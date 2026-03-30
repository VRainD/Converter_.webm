from __future__ import annotations

import asyncio
import json
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.deps import JobsDep, SettingsDep, StorageDep
from app.models.schemas import (
    CreateJobsRequest,
    CreateJobsResponse,
    JobListResponse,
    JobPublic,
    JobStatus,
)
from app.services.storage import sanitize_filename

router = APIRouter(tags=["jobs"])


@router.post("/api/jobs", response_model=CreateJobsResponse)
async def create_jobs(body: CreateJobsRequest, jobs: JobsDep) -> CreateJobsResponse:
    try:
        created = await jobs.create_jobs(body)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return CreateJobsResponse(jobs=created)


@router.get("/api/jobs", response_model=JobListResponse)
def list_jobs(jobs: JobsDep) -> JobListResponse:
    return JobListResponse(jobs=jobs.list_jobs())


@router.get("/api/jobs/{job_id}", response_model=JobPublic)
def get_job(job_id: UUID, jobs: JobsDep) -> JobPublic:
    j = jobs.get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found.")
    return j


@router.get("/api/jobs/{job_id}/progress")
def get_progress(job_id: UUID, jobs: JobsDep) -> JobPublic:
    return get_job(job_id, jobs)


@router.get("/api/jobs/{job_id}/events")
async def job_events(job_id: UUID, jobs: JobsDep) -> EventSourceResponse:
    async def gen():
        last_json = ""
        while True:
            j = jobs.get_job(job_id)
            if not j:
                yield {"event": "error", "data": json.dumps({"error": "Job not found"})}
                break
            payload = j.model_dump_json()
            if payload != last_json:
                last_json = payload
                yield {"event": "job", "data": payload}
            if j.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ):
                break
            await asyncio.sleep(0.35)

    return EventSourceResponse(gen())


@router.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: UUID, jobs: JobsDep) -> dict[str, str]:
    ok = await jobs.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled.")
    return {"status": "cancel_requested"}


@router.delete("/api/jobs/{job_id}")
async def delete_job(job_id: UUID, jobs: JobsDep) -> dict[str, str]:
    ok = await jobs.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"status": "deleted"}


@router.get("/api/jobs/{job_id}/download")
def download_result(job_id: UUID, jobs: JobsDep) -> FileResponse:
    p = jobs.result_path(job_id)
    if not p:
        j = jobs.get_job(job_id)
        if j and j.status not in (JobStatus.COMPLETED,):
            raise HTTPException(status_code=409, detail="Conversion is not finished yet.")
        raise HTTPException(
            status_code=404,
            detail="Result not available. It may have been deleted by cleanup or never completed.",
        )
    fname = sanitize_filename(p.name)
    return FileResponse(
        path=p,
        filename=fname,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
    )


@router.get("/api/jobs/download-zip")
def download_zip(
    jobs: JobsDep,
    ids: str = Query(..., description="Comma-separated job UUIDs"),
) -> StreamingResponse:
    raw = [x.strip() for x in ids.split(",") if x.strip()]
    if not raw:
        raise HTTPException(status_code=400, detail="No job ids provided.")
    paths: list[tuple[str, Path]] = []
    for s in raw:
        try:
            jid = UUID(s)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid UUID: {s}") from e
        p = jobs.result_path(jid)
        if not p:
            raise HTTPException(status_code=404, detail=f"Result not available for job {jid}")
        paths.append((p.name, p))

    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, path in paths:
            zf.write(path, arcname=arcname)
    buf.seek(0)
    data = buf.getvalue()

    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="converted.zip"'},
    )
