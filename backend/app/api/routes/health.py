import shutil

from fastapi import APIRouter

from app.deps import JobsDep, SettingsDep
from app.models.schemas import HealthResponse, SettingsPublic, SystemStatusResponse

router = APIRouter(tags=["health"])


def _which(name: str) -> bool:
    return shutil.which(name) is not None


@router.get("/api/health", response_model=HealthResponse)
def health(settings: SettingsDep) -> HealthResponse:
    ffmpeg_ok = _which("ffmpeg")
    ffprobe_ok = _which("ffprobe")
    return HealthResponse(
        status="ok" if ffmpeg_ok and ffprobe_ok else "degraded",
        ffmpeg_available=ffmpeg_ok,
        ffprobe_available=ffprobe_ok,
    )


@router.get("/api/settings", response_model=SettingsPublic)
def public_settings(settings: SettingsDep) -> SettingsPublic:
    return SettingsPublic(
        max_upload_mb=settings.max_upload_mb,
        max_concurrent_jobs=settings.max_concurrent_jobs,
        enable_advanced_options=settings.enable_advanced_options,
        default_output_format=settings.default_output_format,
        default_quality_profile=settings.default_quality_profile,
        gif_max_duration_sec=settings.gif_max_duration_sec,
        supported_formats=["mp4", "mkv", "avi", "mov", "mpeg", "gif"],
    )


@router.get("/api/status", response_model=SystemStatusResponse)
def system_status(settings: SettingsDep, jobs: JobsDep) -> SystemStatusResponse:
    ffmpeg_ok = _which("ffmpeg")
    ffprobe_ok = _which("ffprobe")
    health = HealthResponse(
        status="ok" if ffmpeg_ok and ffprobe_ok else "degraded",
        ffmpeg_available=ffmpeg_ok,
        ffprobe_available=ffprobe_ok,
    )
    pub = SettingsPublic(
        max_upload_mb=settings.max_upload_mb,
        max_concurrent_jobs=settings.max_concurrent_jobs,
        enable_advanced_options=settings.enable_advanced_options,
        default_output_format=settings.default_output_format,
        default_quality_profile=settings.default_quality_profile,
        gif_max_duration_sec=settings.gif_max_duration_sec,
        supported_formats=["mp4", "mkv", "avi", "mov", "mpeg", "gif"],
    )
    active, queued = jobs.counts()
    return SystemStatusResponse(health=health, settings=pub, active_jobs=active, queued_jobs=queued)
