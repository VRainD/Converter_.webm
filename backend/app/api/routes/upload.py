import uuid
from uuid import UUID

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.deps import SettingsDep, StorageDep
from app.formats import (
    ALLOWED_INPUT_EXTENSIONS,
    file_extension,
    is_allowed_input_extension,
    mime_allowed_for_extension,
)
from app.models.schemas import MediaSummary, UploadEntry, UploadResponse
from app.services.ffmpeg_probe import probe_media
from app.services.storage import sanitize_filename

router = APIRouter(tags=["upload"])


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
    allowed = ", ".join(sorted(ALLOWED_INPUT_EXTENSIONS))

    for uf in files:
        name = sanitize_filename(uf.filename or "video.mp4")
        ext = file_extension(name)
        if not is_allowed_input_extension(ext):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format ({ext or 'no extension'}). "
                f"Allowed: {allowed}. Rejected: {name}",
            )

        if not mime_allowed_for_extension(ext, uf.content_type):
            raise HTTPException(
                status_code=400,
                detail=f"MIME type '{uf.content_type}' does not match extension {ext} for file: {name}",
            )

        uid = uuid.uuid4()
        dest = storage.upload_path(uid, ext)
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

        if size == 0:
            try:
                dest.unlink()
            except OSError:
                pass
            raise HTTPException(status_code=400, detail=f"File is empty: {name}")

        try:
            probe_media(dest)
        except ValueError as e:
            try:
                dest.unlink()
            except OSError:
                pass
            raise HTTPException(
                status_code=400,
                detail=f"Could not read media file '{name}'. It may be corrupted or unsupported. {e}",
            ) from e

        uploads.append(UploadEntry(upload_id=uid, original_filename=name, size_bytes=size))

    return UploadResponse(uploads=uploads)


@router.get("/api/uploads/{upload_id}/metadata", response_model=MediaSummary)
async def upload_metadata(upload_id: UUID, storage: StorageDep) -> MediaSummary:
    dest = storage.find_upload_path(upload_id)
    if not dest or not dest.is_file():
        raise HTTPException(status_code=404, detail="Upload not found.")
    try:
        summary, _ = probe_media(dest)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return summary
