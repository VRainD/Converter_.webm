from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.models.schemas import MediaSummary


def _parse_fps(r_frame_rate: str | None) -> float | None:
    if not r_frame_rate or r_frame_rate in ("0/0", "N/A"):
        return None
    if "/" in r_frame_rate:
        a, b = r_frame_rate.split("/", 1)
        try:
            af, bf = float(a), float(b)
            if bf == 0:
                return None
            return round(af / bf, 3)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(r_frame_rate)
    except ValueError:
        return None


def probe_media(path: Path, timeout: int = 120) -> tuple[MediaSummary, dict[str, Any]]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or "ffprobe failed"
        raise ValueError(err)

    data = json.loads(proc.stdout)
    fmt = data.get("format") or {}
    streams = data.get("streams") or []

    duration = fmt.get("duration")
    try:
        duration_sec = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_sec = None

    size = fmt.get("size")
    try:
        file_size = int(size) if size is not None else path.stat().st_size
    except (TypeError, ValueError, OSError):
        file_size = path.stat().st_size if path.exists() else 0

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width = int(v_stream["width"]) if v_stream and v_stream.get("width") else None
    height = int(v_stream["height"]) if v_stream and v_stream.get("height") else None
    fps = _parse_fps(v_stream.get("r_frame_rate") if v_stream else None)

    summary = MediaSummary(
        duration_sec=duration_sec,
        width=width,
        height=height,
        fps=fps,
        has_video=v_stream is not None,
        has_audio=a_stream is not None,
        video_codec=v_stream.get("codec_name") if v_stream else None,
        audio_codec=a_stream.get("codec_name") if a_stream else None,
        file_size_bytes=file_size,
    )
    return summary, data
