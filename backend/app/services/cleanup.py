from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.models.schemas import JobStatus
from app.services.job_manager import JobManager

logger = logging.getLogger(__name__)


def _parse_iso(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def run_retention_loop(settings: Settings, jobs: JobManager, interval_sec: int = 600) -> None:
    while True:
        try:
            await asyncio.sleep(interval_sec)
            await _purge_completed_jobs(settings, jobs)
            _purge_temp(settings)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Retention task failed")


async def _purge_completed_jobs(settings: Settings, jobs: JobManager) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.job_retention_hours)
    for j in list(jobs.list_jobs()):
        if j.status not in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            continue
        completed = _parse_iso(j.completed_at)
        if completed and completed < cutoff:
            await jobs.delete_job(j.job_id)


def _purge_temp(settings: Settings) -> None:
    cutoff = time.time() - settings.temp_retention_hours * 3600
    for f in settings.temp_dir.glob("*"):
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
            except OSError:
                pass
