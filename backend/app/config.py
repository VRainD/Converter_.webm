from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8080
    data_dir: Path = Path("/app/data")
    max_upload_mb: int = 2048
    max_concurrent_jobs: int = 2
    job_retention_hours: int = 48
    temp_retention_hours: int = 6
    log_level: str = "INFO"
    enable_advanced_options: bool = True
    default_output_format: str = "mp4"
    default_quality_profile: str = "balanced"
    gif_max_duration_sec: int = 120
    ffmpeg_timeout_sec: int = 86400
    cors_origins: str = "*"
    debug: bool = False

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "temp"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
