"""Single source of truth for supported input/output formats."""

from __future__ import annotations

from pathlib import Path

# Popular video containers / extensions accepted on upload.
ALLOWED_INPUT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
        ".wmv",
        ".flv",
        ".mpeg",
        ".mpg",
        ".m4v",
        ".3gp",
        ".ts",
        ".mts",
        ".m2ts",
        ".ogv",
        ".vob",
    }
)

OUTPUT_VIDEO_FORMATS: tuple[str, ...] = ("mp4", "mkv", "avi", "mov", "mpeg", "gif")
OUTPUT_AUDIO_FORMATS: tuple[str, ...] = ("mp3", "wav")

OUTPUT_FORMAT_ALIASES: dict[str, str] = {"waw": "wav"}

ALL_OUTPUT_FORMATS: tuple[str, ...] = OUTPUT_VIDEO_FORMATS + OUTPUT_AUDIO_FORMATS

INPUT_MIME_TYPES: dict[str, str] = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
    ".3gp": "video/3gpp",
    ".ts": "video/mp2t",
    ".mts": "video/mp2t",
    ".m2ts": "video/mp2t",
    ".ogv": "video/ogg",
    ".vob": "video/mpeg",
}

NO_AUDIO_TRACK_ERROR = (
    "В исходном файле не найдена аудиодорожка. Экспорт в аудиоформат невозможен."
)


def file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def is_allowed_input_extension(ext: str) -> bool:
    return ext.lower() in ALLOWED_INPUT_EXTENSIONS


def normalize_output_format(value: str) -> str:
    v = value.lower().strip()
    return OUTPUT_FORMAT_ALIASES.get(v, v)


def is_audio_only_output(fmt: str) -> bool:
    return normalize_output_format(fmt) in OUTPUT_AUDIO_FORMATS


def output_file_extension(fmt: str) -> str:
    n = normalize_output_format(fmt)
    return "mpeg" if n == "mpeg" else n


def mime_allowed_for_extension(ext: str, content_type: str | None) -> bool:
    if not content_type or content_type in ("application/octet-stream", "binary/octet-stream"):
        return True
    ct = content_type.split(";", 1)[0].strip().lower()
    if ct.startswith("video/") or ct.startswith("audio/"):
        return True
    expected = INPUT_MIME_TYPES.get(ext.lower())
    if not expected:
        return True
    return ct == expected


def input_accept_attribute() -> str:
    exts = ",".join(sorted(ALLOWED_INPUT_EXTENSIONS))
    mimes = ",".join(sorted(set(INPUT_MIME_TYPES.values())))
    return f"{exts},{mimes}"
