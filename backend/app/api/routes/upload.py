import uuid
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.deps import SettingsDep, StorageDep
from app.models.schemas import MediaSummary, UploadEntry, UploadResponse
from app.services.ffmpeg_probe import probe_media
from app.services.storage import sanitize_filename

router = APIRouter(tags=["upload"])

WEBM_MAGIC = b"\x1a\x45\xdf\xa3"


async def _read_magic(path: Path, n: int = 4) -> bytes:
    async with aiofiles.open(path, "rb") as f:
        return await f.read(n)


@router.post("/api/upload", response_model=UploadResponse)
async def upload_files(
    settings: SettingsDep,
    storage: StorageDep,
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    uploads: list[UploadEntry] = []

    for uf in files:
        name = sanitize_filename(uf.filename or "video.webm")
        if not name.lower().endswith(".webm"):
            raise HTTPException(
                status_code=400,
                detail=f"Only .webm files are accepted. Rejected: {name}",
            )

        uid = uuid.uuid4()
        dest = storage.upload_path(uid)
        size = 0
        chunk = 1024 * 1024
        try:
            async with aiofiles.open(dest, "wb") as out:
                while True:
                    part = await uf.read(chunk)
                    if not part:
                        break
                    size += len(part)
                    if size > max_bytes:
                        try:
                            dest.unlink()
                        except OSError:
                            pass
                        raise HTTPException(
                            status_code=413,
                            detail=f"File too large. Maximum size is {settings.max_upload_mb} MB.",
                        )
                    await out.write(part)
        except HTTPException:
            raise
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Could not save upload: {e}") from e

        magic = await _read_magic(dest)
        if len(magic) < 4 or magic[:4] != WEBM_MAGIC:
            try:
                dest.unlink()
            except OSError:
                pass
            raise HTTPException(
                status_code=400,
                detail=f"File does not look like a valid WebM (EBML header missing): {name}",
            )

        uploads.append(UploadEntry(upload_id=uid, original_filename=name, size_bytes=size))

    return UploadResponse(uploads=uploads)


@router.get("/api/uploads/{upload_id}/metadata", response_model=MediaSummary)
async def upload_metadata(upload_id: UUID, storage: StorageDep) -> MediaSummary:
    dest = storage.upload_path(upload_id)
    if not dest.is_file():
        raise HTTPException(status_code=404, detail="Upload not found.")
    try:
        summary, _ = probe_media(dest)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return summary
