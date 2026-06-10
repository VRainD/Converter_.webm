from app.formats import file_extension, is_allowed_input_extension, mime_allowed_for_extension


def test_webm_input_accepted() -> None:
    assert is_allowed_input_extension(".webm")


def test_mp4_mov_mkv_accepted() -> None:
    for name in ("video.mp4", "clip.MOV", "movie.mkv"):
        assert is_allowed_input_extension(file_extension(name))


def test_mime_video_wildcard_allowed() -> None:
    assert mime_allowed_for_extension(".mp4", "video/mp4")
    assert mime_allowed_for_extension(".mkv", "video/x-matroska")


def test_mime_mismatch_rejected() -> None:
    assert not mime_allowed_for_extension(".mp4", "application/pdf")
