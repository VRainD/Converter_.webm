from pathlib import Path

import pytest

from app.formats import NO_AUDIO_TRACK_ERROR
from app.models.schemas import AdvancedOptions, OutputFormat, QualityProfile
from app.services.ffmpeg_convert import build_ffmpeg_args
from app.services.ffmpeg_probe import probe_timeout_for_size


def _base_args(
    out_fmt: OutputFormat,
    out_name: str,
    has_audio: bool,
    tmp_path: Path,
    audio_codec: str | None = None,
    large_source: bool = False,
) -> tuple[Path, Path, list[str], str | None]:
    inp = tmp_path / "input.mp4"
    inp.write_bytes(b"\x00")
    out = tmp_path / out_name
    args, warn = build_ffmpeg_args(
        inp,
        out,
        out_fmt,
        QualityProfile.BALANCED,
        duration_sec=30.0,
        media_width=1280,
        media_height=720,
        media_fps=30.0,
        has_audio=has_audio,
        advanced=AdvancedOptions(),
        gif_max_duration_sec=120,
        audio_codec=audio_codec,
        large_source=large_source,
    )
    return inp, out, args, warn


def test_mp4_video_conversion_args(tmp_path: Path) -> None:
    _, _, args, _ = _base_args(OutputFormat.MP4, "out.mp4", True, tmp_path)
    assert "libx264" in args
    assert "-c:v" in args


def test_mp3_audio_reencode_args(tmp_path: Path) -> None:
    _, _, args, warn = _base_args(OutputFormat.MP3, "out.mp3", True, tmp_path, audio_codec="aac")
    assert "-vn" in args
    assert "-map" in args
    assert "libmp3lame" in args
    assert "-b:a" in args
    assert "192k" in args
    assert "libx264" not in args
    assert warn is not None


def test_mp3_stream_copy_when_source_is_mp3(tmp_path: Path) -> None:
    _, _, args, warn = _base_args(OutputFormat.MP3, "out.mp3", True, tmp_path, audio_codec="mp3")
    assert "-c:a" in args
    assert "copy" in args
    assert "libmp3lame" not in args
    assert warn and "stream copy" in warn.lower()


def test_wav_audio_only_args(tmp_path: Path) -> None:
    _, _, args, _ = _base_args(OutputFormat.WAV, "out.wav", True, tmp_path, audio_codec="aac")
    assert "-vn" in args
    assert "pcm_s16le" in args
    assert "libx264" not in args


def test_large_source_adds_probe_flags(tmp_path: Path) -> None:
    _, _, args, _ = _base_args(OutputFormat.MP3, "out.mp3", True, tmp_path, large_source=True)
    assert "-probesize" in args
    assert "-analyzeduration" in args


def test_audio_export_without_audio_track_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=NO_AUDIO_TRACK_ERROR):
        _base_args(OutputFormat.MP3, "out.mp3", False, tmp_path)


def test_probe_timeout_scales_with_size() -> None:
    assert probe_timeout_for_size(100 * 1024**2) == 120
    assert probe_timeout_for_size(2 * 1024**3) >= 300
    assert probe_timeout_for_size(30 * 1024**3) >= 900
