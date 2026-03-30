from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings
from app.models.schemas import (
    AdvancedOptions,
    CreateJobsRequest,
    JobProgress,
    JobPublic,
    JobStatus,
    MediaSummary,
    OutputFormat,
    QualityProfile,
)
from app.services.ffmpeg_convert import (
    build_ffmpeg_args,
    humanize_ffmpeg_error,
    run_ffmpeg_with_progress,
)
from app.services.ffmpeg_probe import probe_media
from app.services.storage import StorageService, sanitize_filename

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JobRecord:
    public: JobPublic
    upload_id: uuid.UUID
    advanced: AdvancedOptions
    cancel_event: threading.Event = field(default_factory=threading.Event)
    progress_lock: threading.Lock = field(default_factory=threading.Lock)


class JobManager:
    def __init__(self, settings: Settings, storage: StorageService) -> None:
        self._s = settings
        self._storage = storage
        self._jobs: dict[uuid.UUID, JobRecord] = {}
        self._queue: asyncio.Queue[uuid.UUID] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        n = max(1, self._s.max_concurrent_jobs)
        for _ in range(n):
            self._workers.append(asyncio.create_task(self._worker_loop()))

    async def stop(self) -> None:
        for t in self._workers:
            t.cancel()
        self._workers.clear()
        self._started = False

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await asyncio.to_thread(self._run_job_sync, job_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker failed for job %s", job_id)
            finally:
                self._queue.task_done()

    def _run_job_sync(self, job_id: uuid.UUID) -> None:
        rec = self._jobs.get(job_id)
        if not rec:
            return
        if rec.cancel_event.is_set():
            rec.public.status = JobStatus.CANCELLED
            rec.public.error_message = "Cancelled before start."
            rec.public.completed_at = _utcnow()
            rec.public.updated_at = _utcnow()
            return

        upload_path = self._storage.upload_path(rec.upload_id)
        if not upload_path.is_file():
            self._fail(rec, "Upload file is missing. It may have expired or been removed.")
            return

        rec.public.status = JobStatus.ANALYZING
        rec.public.updated_at = _utcnow()
        try:
            summary, _ = probe_media(upload_path)
        except ValueError as e:
            self._fail(rec, f"Could not read media file: {e}")
            return

        rec.public.media_summary = summary
        rec.public.updated_at = _utcnow()

        out_fmt = rec.public.output_format
        if (
            out_fmt == OutputFormat.GIF
            and summary.duration_sec
            and summary.duration_sec > self._s.gif_max_duration_sec
        ):
            self._fail(
                rec,
                f"GIF: maximum duration is {self._s.gif_max_duration_sec}s "
                f"(this file is ~{summary.duration_sec:.0f}s).",
            )
            return

        if not summary.has_video:
            self._fail(rec, "No video track found. Nothing to convert.")
            return

        if upload_path.stat().st_size == 0:
            self._fail(rec, "File is empty.")
            return

        ext = out_fmt.value if out_fmt != OutputFormat.MPEG else "mpeg"
        base_name = Path(rec.public.original_filename).stem
        safe = sanitize_filename(f"{base_name}.{ext}")
        job_dir = self._storage.job_dir(job_id)
        out_path = job_dir / safe

        if out_path.exists():
            stem = Path(safe).stem
            suf = Path(safe).suffix
            safe = f"{stem}_{job_id.hex[:8]}{suf}"
            out_path = job_dir / safe

        advanced = rec.advanced

        try:
            argv, warn = build_ffmpeg_args(
                upload_path,
                out_path,
                out_fmt,
                rec.public.quality,
                summary.duration_sec,
                summary.width,
                summary.height,
                summary.fps,
                summary.has_audio,
                advanced,
                self._s.gif_max_duration_sec,
            )
        except ValueError as e:
            self._fail(rec, str(e))
            return

        if warn:
            rec.public.progress = JobProgress(message=warn)

        rec.public.status = JobStatus.CONVERTING
        if not rec.public.started_at:
            rec.public.started_at = _utcnow()
        rec.public.updated_at = _utcnow()

        log_path = self._storage.job_log_path(job_id)
        try:
            log_path.write_text("", encoding="utf-8")
        except OSError:
            pass

        duration = summary.duration_sec

        def on_progress(data: dict[str, Any]) -> None:
            with rec.progress_lock:
                p = rec.public.progress
                if "percent" in data and data["percent"] is not None:
                    p.percent = round(float(data["percent"]), 1)
                if data.get("out_time_sec") is not None:
                    p.out_time_sec = float(data["out_time_sec"])
                if data.get("eta_sec") is not None:
                    try:
                        p.eta_sec = float(data["eta_sec"])
                    except (TypeError, ValueError):
                        pass
                if data.get("speed"):
                    p.speed = str(data["speed"])
                p.stage = "encoding"
                rec.public.updated_at = _utcnow()

        code, err_tail = run_ffmpeg_with_progress(
            argv,
            duration,
            on_progress,
            log_path,
            rec.cancel_event,
            self._s.ffmpeg_timeout_sec,
        )

        if rec.cancel_event.is_set() or code == -1:
            rec.public.status = JobStatus.CANCELLED
            rec.public.error_message = "Conversion was cancelled."
            rec.public.completed_at = _utcnow()
            rec.public.updated_at = _utcnow()
            self._cleanup_partial(out_path)
            return

        if code == -2:
            self._fail(rec, err_tail)
            self._cleanup_partial(out_path)
            return

        if code != 0:
            msg = humanize_ffmpeg_error(code, err_tail)
            self._fail(rec, msg or f"ffmpeg failed with exit code {code}.")
            self._cleanup_partial(out_path)
            return

        rec.public.status = JobStatus.FINALIZING
        rec.public.updated_at = _utcnow()
        if not out_path.is_file() or out_path.stat().st_size == 0:
            self._fail(rec, "Output file was not created or is empty.")
            self._cleanup_partial(out_path)
            return

        rec.public.result_filename = out_path.name
        rec.public.result_size_bytes = out_path.stat().st_size
        rec.public.progress = JobProgress(percent=100.0, stage="done", message="")
        rec.public.status = JobStatus.COMPLETED
        rec.public.completed_at = _utcnow()
        rec.public.updated_at = _utcnow()
        try:
            self._storage.delete_upload(rec.upload_id)
        except OSError:
            logger.warning("Could not delete upload %s", rec.upload_id)

    def _cleanup_partial(self, out_path: Path) -> None:
        if out_path.is_file():
            try:
                out_path.unlink()
            except OSError:
                pass

    def _fail(self, rec: JobRecord, message: str, detail: str | None = None) -> None:
        rec.public.status = JobStatus.FAILED
        rec.public.error_message = message
        rec.public.error_detail = detail
        rec.public.completed_at = _utcnow()
        rec.public.updated_at = _utcnow()

    async def create_jobs(self, req: CreateJobsRequest) -> list[JobPublic]:
        adv_in = req.advanced or AdvancedOptions()
        out: list[JobPublic] = []
        for item in req.items:
            uid = item.upload_id
            if not self._storage.upload_path(uid).is_file():
                raise FileNotFoundError(f"Upload not found: {uid}")

            up_path = self._storage.upload_path(uid)
            size = up_path.stat().st_size
            jid = uuid.uuid4()
            now = _utcnow()
            jp = JobPublic(
                job_id=jid,
                status=JobStatus.QUEUED,
                original_filename=item.original_filename,
                source_size_bytes=size,
                output_format=req.output_format,
                quality=req.quality,
                created_at=now,
                updated_at=now,
                media_summary=MediaSummary(file_size_bytes=size),
            )
            rec = JobRecord(public=jp, upload_id=uid, advanced=adv_in)
            self._jobs[jid] = rec
            await self._queue.put(jid)
            out.append(jp)
        return out

    def get_job(self, job_id: uuid.UUID) -> JobPublic | None:
        rec = self._jobs.get(job_id)
        return rec.public if rec else None

    def list_jobs(self) -> list[JobPublic]:
        return [r.public for r in self._jobs.values()]

    async def cancel_job(self, job_id: uuid.UUID) -> bool:
        rec = self._jobs.get(job_id)
        if not rec:
            return False
        if rec.public.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False
        rec.cancel_event.set()
        return True

    async def delete_job(self, job_id: uuid.UUID) -> bool:
        rec = self._jobs.pop(job_id, None)
        if not rec:
            return False
        rec.cancel_event.set()
        self._storage.delete_job_artifacts(job_id)
        try:
            self._storage.delete_upload(rec.upload_id)
        except OSError:
            pass
        return True

    def result_path(self, job_id: uuid.UUID) -> Path | None:
        rec = self._jobs.get(job_id)
        if not rec or rec.public.status != JobStatus.COMPLETED or not rec.public.result_filename:
            return None
        p = self._storage.job_dir(job_id) / rec.public.result_filename
        if p.is_file():
            return p
        return None

    def counts(self) -> tuple[int, int]:
        active = sum(
            1
            for r in self._jobs.values()
            if r.public.status in (JobStatus.ANALYZING, JobStatus.CONVERTING, JobStatus.FINALIZING)
        )
        queued = sum(1 for r in self._jobs.values() if r.public.status == JobStatus.QUEUED)
        return active, queued
