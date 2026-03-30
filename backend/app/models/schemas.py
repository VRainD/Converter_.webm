from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    ANALYZING = "analyzing"
    CONVERTING = "converting"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputFormat(str, Enum):
    MP4 = "mp4"
    MKV = "mkv"
    AVI = "avi"
    MOV = "mov"
    MPEG = "mpeg"
    GIF = "gif"


class QualityProfile(str, Enum):
    SOURCE_LIKE = "source_like"
    HIGH = "high"
    BALANCED = "balanced"
    SMALL = "small"


class ResolutionPreset(str, Enum):
    ORIGINAL = "original"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"


class FpsPreset(str, Enum):
    KEEP = "keep"
    F30 = "30"
    F25 = "25"
    F24 = "24"


class AudioMode(str, Enum):
    KEEP = "keep"
    REMOVE = "remove"


class OverwritePolicy(str, Enum):
    RENAME = "rename"
    REPLACE = "replace"


class MediaSummary(BaseModel):
    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    has_video: bool = False
    has_audio: bool = False
    video_codec: str | None = None
    audio_codec: str | None = None
    file_size_bytes: int = 0


class JobProgress(BaseModel):
    percent: float | None = None
    stage: str = ""
    message: str = ""
    eta_sec: float | None = None
    out_time_sec: float | None = None
    speed: str | None = None


class JobPublic(BaseModel):
    job_id: UUID
    status: JobStatus
    original_filename: str
    source_size_bytes: int
    output_format: OutputFormat
    quality: QualityProfile
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    media_summary: MediaSummary | None = None
    progress: JobProgress = Field(default_factory=JobProgress)
    result_filename: str | None = None
    result_size_bytes: int | None = None
    error_message: str | None = None
    error_detail: str | None = None


class UploadEntry(BaseModel):
    upload_id: UUID
    original_filename: str
    size_bytes: int


class UploadResponse(BaseModel):
    uploads: list[UploadEntry]


class AdvancedOptions(BaseModel):
    resolution: ResolutionPreset = ResolutionPreset.ORIGINAL
    fps: FpsPreset = FpsPreset.KEEP
    audio: AudioMode = AudioMode.KEEP
    overwrite: OverwritePolicy = OverwritePolicy.RENAME


class JobItem(BaseModel):
    upload_id: UUID
    original_filename: str


class CreateJobsRequest(BaseModel):
    items: list[JobItem] = Field(min_length=1)
    output_format: OutputFormat
    quality: QualityProfile
    advanced: AdvancedOptions | None = None


class CreateJobsResponse(BaseModel):
    jobs: list[JobPublic]


class JobListResponse(BaseModel):
    jobs: list[JobPublic]


class HealthResponse(BaseModel):
    status: str
    ffmpeg_available: bool
    ffprobe_available: bool
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: str | None = None


class SettingsPublic(BaseModel):
    max_upload_mb: int
    max_concurrent_jobs: int
    enable_advanced_options: bool
    default_output_format: str
    default_quality_profile: str
    gif_max_duration_sec: int
    supported_formats: list[str]


class SystemStatusResponse(BaseModel):
    health: HealthResponse
    settings: SettingsPublic
    active_jobs: int
    queued_jobs: int
