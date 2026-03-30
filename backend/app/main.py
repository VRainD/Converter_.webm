from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import health, jobs, upload
from app.config import get_settings
from app.services.cleanup import run_retention_loop
from app.services.job_manager import JobManager
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    storage = StorageService(settings)
    jm = JobManager(settings, storage)
    app.state.storage = storage
    app.state.jobs = jm
    await jm.start()
    retention_task = asyncio.create_task(run_retention_loop(settings, jm))
    yield
    retention_task.cancel()
    await jm.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="WebM Converter",
        version="1.0.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins != ["*"] else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(upload.router)
    app.include_router(jobs.router)

    static_dir = Path(__file__).resolve().parent.parent / "static"
    index = static_dir / "index.html"
    if static_dir.is_dir() and index.is_file():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/")
        async def root_index():
            return FileResponse(index)

        @app.get("/status-page")
        async def status_page():
            return FileResponse(index)

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            if full_path.startswith("api"):
                raise HTTPException(status_code=404)
            return FileResponse(index)

    return app


app = create_app()
