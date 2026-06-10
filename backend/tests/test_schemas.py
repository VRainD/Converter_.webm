from uuid import uuid4

from app.models.schemas import CreateJobsRequest, JobItem, OutputFormat, QualityProfile


def test_create_jobs_request_normalizes_waw_alias() -> None:
    req = CreateJobsRequest(
        items=[JobItem(upload_id=uuid4(), original_filename="clip.mp4")],
        output_format="waw",  # type: ignore[arg-type]
        quality=QualityProfile.BALANCED,
    )
    assert req.output_format == OutputFormat.WAV


def test_create_jobs_request_accepts_mp3() -> None:
    req = CreateJobsRequest(
        items=[JobItem(upload_id=uuid4(), original_filename="clip.mov")],
        output_format=OutputFormat.MP3,
        quality=QualityProfile.BALANCED,
    )
    assert req.output_format == OutputFormat.MP3
