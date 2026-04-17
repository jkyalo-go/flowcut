import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio


def test_run_scene_detection_returns_list(tmp_path):
    scene0_start = MagicMock()
    scene0_start.get_seconds.return_value = 0.0
    scene0_end = MagicMock()
    scene0_end.get_seconds.return_value = 5.0
    scene1_start = MagicMock()
    scene1_start.get_seconds.return_value = 5.0
    scene1_end = MagicMock()
    scene1_end.get_seconds.return_value = 12.3
    fake_scene = [(scene0_start, scene0_end), (scene1_start, scene1_end)]
    with patch("services.sie.workers.detect", return_value=fake_scene):
        from services.sie.workers import run_scene_detection
        result = asyncio.get_event_loop().run_until_complete(run_scene_detection("/fake/video.mp4"))
    assert len(result) == 2
    assert result[0]["start_sec"] == 0.0
    assert result[1]["end_sec"] == 12.3


def test_run_transcription_uses_singleton():
    """WhisperModel is only instantiated once across multiple calls."""
    import services.sie.workers as _workers
    _workers._whisper_model = None  # reset singleton for test isolation
    fake_model = MagicMock()
    fake_model.transcribe.return_value = (
        [MagicMock(start=0.0, end=3.0, text=" Hello world")],
        MagicMock(),
    )
    with patch("services.sie.workers.WhisperModel", return_value=fake_model) as mock_cls:
        from services.sie.workers import run_transcription
        asyncio.get_event_loop().run_until_complete(run_transcription("/fake/video.mp4"))
        asyncio.get_event_loop().run_until_complete(run_transcription("/fake/video.mp4"))
    mock_cls.assert_called_once()


def test_run_gemini_visual_scoring_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from services.sie.workers import run_gemini_visual_scoring
    result = asyncio.get_event_loop().run_until_complete(run_gemini_visual_scoring("/fake/video.mp4"))
    assert result == []


def test_run_all_workers_tolerates_worker_failure():
    """If one worker raises, run_all_workers returns empty for that field, not a crash."""
    async def _raise(*a, **kw):
        raise RuntimeError("scene detection failed")

    with patch("services.sie.workers.run_scene_detection", side_effect=_raise), \
         patch("services.sie.workers.run_transcription", return_value={"text": "", "segments": []}), \
         patch("services.sie.workers.run_gemini_visual_scoring", return_value=[]):
        from services.sie.workers import run_all_workers
        result = asyncio.get_event_loop().run_until_complete(run_all_workers("/fake/video.mp4"))
    assert result["scenes"] == []
    assert result["transcript"] == {"text": "", "segments": []}
