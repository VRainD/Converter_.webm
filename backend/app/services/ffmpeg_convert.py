from __future__ import annotations

import json
import os
import re
import select
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.models.schemas import (
    AdvancedOptions,
    AudioMode,
    FpsPreset,
    OutputFormat,
    QualityProfile,
    ResolutionPreset,
)

ProgressCb = Callable[[dict[str, Any]], None]


def _crf_for_quality(q: QualityProfile) -> int:
    mapping = {
        QualityProfile.SOURCE_LIKE: 20,
        QualityProfile.HIGH: 18,
        QualityProfile.BALANCED: 23,
        QualityProfile.SMALL: 28,
    }
    return mapping[q]


def _preset_for_quality(q: QualityProfile) -> str:
    if q == QualityProfile.SMALL:
        return "faster"
    if q == QualityProfile.HIGH:
        return "slow"
    return "medium"


def _scale_filter(res: ResolutionPreset, w: int | None, h: int | None) -> str | None:
    if res == ResolutionPreset.ORIGINAL:
        return None
    target_h = {"1080p": 1080, "720p": 720, "480p": 480}[res.value]
    if not h or not w:
        return f"scale=-2:{target_h}:flags=lanczos"
    if h <= target_h:
        return None
    return f"scale=-2:{target_h}:flags=lanczos"


def _fps_filter(fps: FpsPreset, source_fps: float | None) -> str | None:
    if fps == FpsPreset.KEEP:
        return None
    target = float(fps.value)
    if source_fps and abs(source_fps - target) < 0.01:
        return None
    return f"fps={target}"


def _combine_vf(parts: list[str]) -> list[str]:
    filt = ",".join(p for p in parts if p)
    if not filt:
        return []
    return ["-vf", filt]


def build_ffmpeg_args(
    input_path: Path,
    output_path: Path,
    output_format: OutputFormat,
    quality: QualityProfile,
    duration_sec: float | None,
    media_width: int | None,
    media_height: int | None,
    media_fps: float | None,
    has_audio: bool,
    advanced: AdvancedOptions | None,
    gif_max_duration_sec: int,
) -> tuple[list[str], str | None]:
    """Returns argv list and optional human-readable warning."""
    adv = advanced or AdvancedOptions()
    warning: str | None = None

    crf = _crf_for_quality(quality)
    preset = _preset_for_quality(quality)

    vf_parts: list[str] = []
    sf = _scale_filter(adv.resolution, media_width, media_height)
    if sf:
        vf_parts.append(sf)
    ff = _fps_filter(adv.fps, media_fps)
    if ff:
        vf_parts.append(ff)

    vf_arg = _combine_vf(vf_parts)

    audio_keep = adv.audio == AudioMode.KEEP and has_audio
    if output_format == OutputFormat.GIF:
        if duration_sec is not None and duration_sec > gif_max_duration_sec:
            raise ValueError(
                f"GIF: maximum duration is {gif_max_duration_sec} seconds "
                f"(file is ~{duration_sec:.0f}s). Shorten the clip or choose another format."
            )
        if has_audio and audio_keep:
            warning = "GIF has no audio; audio was omitted."
        audio_keep = False

    base_before: list[str] = ["ffmpeg", "-hide_banner", "-y", "-i", str(input_path)]

    if output_format == OutputFormat.MP4:
        args = base_before + vf_arg
        args += [
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]
        if audio_keep:
            args += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        else:
            args += ["-an"]
        args += [str(output_path)]
        return args, warning

    if output_format == OutputFormat.MKV:
        args = base_before + vf_arg
        args += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if audio_keep:
            args += ["-c:a", "aac", "-b:a", "192k"]
        else:
            args += ["-an"]
        args += [str(output_path)]
        return args, warning

    if output_format == OutputFormat.MOV:
        args = base_before + vf_arg
        args += [
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
        ]
        if audio_keep:
            args += ["-c:a", "aac", "-b:a", "192k"]
        else:
            args += ["-an"]
        args += [str(output_path)]
        return args, warning

    if output_format == OutputFormat.AVI:
        warning = (
            "AVI is a legacy container; files may be large and compatibility varies. "
            "Prefer MP4 or MKV when possible."
        )
        args = base_before + vf_arg
        args += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if audio_keep:
            args += ["-c:a", "libmp3lame", "-b:a", "192k"]
        else:
            args += ["-an"]
        args += [str(output_path)]
        return args, warning

    if output_format == OutputFormat.MPEG:
        args = base_before + vf_arg
        args += ["-c:v", "mpeg2video", "-q:v", "4"]
        if audio_keep:
            args += ["-c:a", "mp2", "-b:a", "192k"]
        else:
            args += ["-an"]
        args += ["-f", "mpeg", str(output_path)]
        return args, warning

    if output_format == OutputFormat.GIF:
        palette = str(output_path.with_suffix(".palette.png"))
        scale_gif = "fps=12,scale=480:-1:flags=lanczos"
        if vf_parts:
            scale_gif = f"{','.join(vf_parts)},{scale_gif}"
        args1 = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"{scale_gif},palettegen=stats_mode=diff",
            palette,
        ]
        args2 = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(input_path),
            "-i",
            palette,
            "-lavfi",
            f"{scale_gif} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5",
            str(output_path),
        ]
        return ["__GIF_TWO_PASS__", json.dumps(args1), json.dumps(args2), palette], warning

    raise ValueError(f"Unsupported format: {output_format}")


def run_ffmpeg_with_progress(
    argv: list[str],
    duration_sec: float | None,
    on_progress: ProgressCb,
    log_path: Path | None,
    cancel_event: threading.Event,
    timeout_sec: int,
) -> tuple[int, str]:
    """Run ffmpeg; parse -progress from pipe. Returns (returncode, stderr_tail)."""
    if argv and argv[0] == "__GIF_TWO_PASS__":
        args1 = json.loads(argv[1])
        args2 = json.loads(argv[2])
        palette_path = Path(argv[3])
        code, err = _run_single_ffmpeg(
            args1, duration_sec, on_progress, log_path, cancel_event, timeout_sec
        )
        if code != 0:
            return code, err
        try:
            code2, err2 = _run_single_ffmpeg(
                args2, duration_sec, on_progress, log_path, cancel_event, timeout_sec
            )
            return code2, err2
        finally:
            if palette_path.is_file():
                try:
                    palette_path.unlink()
                except OSError:
                    pass

    return _run_single_ffmpeg(argv, duration_sec, on_progress, log_path, cancel_event, timeout_sec)


def _run_single_ffmpeg(
    argv: list[str],
    duration_sec: float | None,
    on_progress: ProgressCb,
    log_path: Path | None,
    cancel_event: threading.Event,
    timeout_sec: int,
) -> tuple[int, str]:
    prog_args = argv[:]
    if "-progress" not in prog_args:
        insert_at = 1
        for i, a in enumerate(prog_args):
            if a == "-i":
                insert_at = i
                break
        prog_args[insert_at:insert_at] = ["-progress", "pipe:1", "-nostats"]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        prog_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        bufsize=0,
    )
    stderr_chunks: list[bytes] = []
    progress_buf = b""

    def read_stderr() -> None:
        assert proc.stderr
        while True:
            chunk = proc.stderr.read(4096)
            if not chunk:
                break
            stderr_chunks.append(chunk)
            if log_path:
                try:
                    with open(log_path, "ab") as lf:
                        lf.write(chunk)
                except OSError:
                    pass

    t_err = threading.Thread(target=read_stderr, daemon=True)
    t_err.start()

    start = time.monotonic()
    last_emit = 0.0

    assert proc.stdout
    while True:
        if cancel_event.is_set():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            t_err.join(timeout=2)
            return -1, "Cancelled"

        if time.monotonic() - start > timeout_sec:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            t_err.join(timeout=2)
            return -2, f"Timed out after {timeout_sec} seconds"

        ready, _, _ = select.select([proc.stdout], [], [], 0.5)
        if ready:
            chunk = proc.stdout.read(4096)
            if not chunk:
                break
            progress_buf += chunk
            while b"\n" in progress_buf:
                line, progress_buf = progress_buf.split(b"\n", 1)
                try:
                    text = line.decode("utf-8", errors="replace").strip()
                except Exception:
                    continue
                if "=" in text:
                    k, v = text.split("=", 1)
                    if k == "out_time_ms":
                        try:
                            out_us = int(v)
                            out_sec = out_us / 1_000_000.0
                            pct = None
                            if duration_sec and duration_sec > 0:
                                pct = min(99.9, max(0.0, (out_sec / duration_sec) * 100.0))
                            now = time.monotonic()
                            if now - last_emit > 0.2 or pct is not None:
                                last_emit = now
                                eta = None
                                if duration_sec and duration_sec > 0 and out_sec < duration_sec:
                                    rate = out_sec / max(now - start, 1e-6)
                                    if rate > 0:
                                        eta = (duration_sec - out_sec) / rate
                                on_progress(
                                    {
                                        "out_time_sec": out_sec,
                                        "percent": pct,
                                        "eta_sec": eta,
                                    }
                                )
                        except (ValueError, TypeError):
                            pass
                    elif k == "speed":
                        on_progress({"speed": v})
                    elif k == "progress" and v == "end":
                        on_progress({"percent": 100.0 if duration_sec else None, "stage": "end"})

        if proc.poll() is not None:
            extra = proc.stdout.read() if proc.stdout else b""
            if extra:
                progress_buf += extra
            break

    t_err.join(timeout=30)
    err_tail = b"".join(stderr_chunks)[-8000:].decode("utf-8", errors="replace")
    code = proc.wait()
    return code, err_tail


_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")


def humanize_ffmpeg_error(code: int, stderr_tail: str) -> str:
    if code == 0:
        return ""
    lines = [ln.strip() for ln in stderr_tail.splitlines() if ln.strip()]
    meaningful = [ln for ln in lines if any(x in ln.lower() for x in ("error", "invalid", "failed", "cannot"))]
    pick = meaningful[-3:] if meaningful else lines[-5:]
    msg = " ".join(pick) if pick else f"ffmpeg exited with code {code}"
    if len(msg) > 600:
        msg = msg[:600] + "…"
    return msg
