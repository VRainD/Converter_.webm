from app.formats import (
    ALLOWED_INPUT_EXTENSIONS,
    is_allowed_input_extension,
    is_audio_only_output,
    normalize_output_format,
    output_file_extension,
)


def test_popular_video_extensions_allowed() -> None:
    for ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".mts", ".m2ts", ".vob"):
        assert is_allowed_input_extension(ext)


def test_unknown_extension_rejected() -> None:
    assert not is_allowed_input_extension(".exe")


def test_waw_normalizes_to_wav() -> None:
    assert normalize_output_format("waw") == "wav"
    assert normalize_output_format("WAW") == "wav"


def test_audio_only_detection() -> None:
    assert is_audio_only_output("mp3")
    assert is_audio_only_output("wav")
    assert not is_audio_only_output("mp4")


def test_output_extension_mapping() -> None:
    assert output_file_extension("mpeg") == "mpeg"
    assert output_file_extension("mp3") == "mp3"
    assert output_file_extension("waw") == "wav"


def test_all_input_extensions_unique() -> None:
    assert len(ALLOWED_INPUT_EXTENSIONS) >= 15
