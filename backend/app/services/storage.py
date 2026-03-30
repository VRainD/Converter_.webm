from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from app.config import Settings

SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._\-() ]+")


def sanitize_filename(name: str, max_len: int = 180) -> str:
    base = Path(name).name
    base = SAFE_NAME_RE.sub("_", base)
    if not base or base.strip() == "":
        base = "file"
    if len(base) > max_len:
        stem = Path(base).stem[: max_len - 8]
        suf = Path(base).suffix
        base = f"{stem}{suf}"
    return base


def ensure_under(base: Path, candidate: Path) -> Path:
    base = base.resolve()
    cand = candidate.resolve()
    try:
        cand.relative_to(base)
    except ValueError as e:
        raise PermissionError("Path traversal blocked") from e
    return cand


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        for d in (settings.uploads_dir, settings.outputs_dir, settings.temp_dir, settings.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

    def upload_path(self, upload_id: uuid.UUID) -> Path:
        p = self._s.uploads_dir / f"{upload_id}.webm"
        return ensure_under(self._s.uploads_dir, p)

    def job_dir(self, job_id: uuid.UUID) -> Path:
        p = self._s.outputs_dir / str(job_id)
        p.mkdir(parents=True, exist_ok=True)
        return ensure_under(self._s.outputs_dir, p)

    def job_log_path(self, job_id: uuid.UUID) -> Path:
        p = self._s.logs_dir / f"job-{job_id}.log"
        return ensure_under(self._s.logs_dir, p)

    def temp_path(self, job_id: uuid.UUID, suffix: str) -> Path:
        self._s.temp_dir.mkdir(parents=True, exist_ok=True)
        p = self._s.temp_dir / f"{job_id}_{suffix}"
        return ensure_under(self._s.temp_dir, p)

    def delete_upload(self, upload_id: uuid.UUID) -> None:
        p = self.upload_path(upload_id)
        if p.is_file():
            p.unlink()

    def delete_job_artifacts(self, job_id: uuid.UUID) -> None:
        d = self._s.outputs_dir / str(job_id)
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
        lp = self.job_log_path(job_id)
        if lp.is_file():
            lp.unlink()
        for f in self._s.temp_dir.glob(f"{job_id}_*"):
            if f.is_file():
                try:
                    f.unlink()
                except OSError:
                    pass
