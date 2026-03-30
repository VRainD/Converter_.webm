from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.services.job_manager import JobManager
from app.services.storage import StorageService


def get_storage(request: Request) -> StorageService:
    return request.app.state.storage


def get_jobs(request: Request) -> JobManager:
    return request.app.state.jobs


SettingsDep = Annotated[Settings, Depends(get_settings)]
StorageDep = Annotated[StorageService, Depends(get_storage)]
JobsDep = Annotated[JobManager, Depends(get_jobs)]
