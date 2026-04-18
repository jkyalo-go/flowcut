import pytest
from pydantic import ValidationError

from services.sie.schemas import CaptionSegment, EditManifest, TrimAction, ZoomAction


def test_edit_manifest_valid_minimal():
    m = EditManifest(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok"],
        confidence=0.85,
        reasoning="Strong hook with visual peak at 5s.",
    )
    assert m.trim.end_sec == 30.0
    assert m.confidence == 0.85


def test_edit_manifest_confidence_bounds():
    with pytest.raises(ValidationError):
        EditManifest(
            trim=TrimAction(start_sec=0.0, end_sec=30.0),
            platform_targets=["tiktok"],
            confidence=1.5,  # out of range
            reasoning="x",
        )


def test_zoom_curve_enum():
    z = ZoomAction(at_sec=5.0, factor=1.5, duration_sec=0.3, curve="ease_out")
    assert z.curve == "ease_out"
    with pytest.raises(ValidationError):
        ZoomAction(at_sec=5.0, factor=1.5, duration_sec=0.3, curve="rocket")


def test_caption_segment_defaults():
    c = CaptionSegment(start_sec=0.0, end_sec=3.0, text="No way!")
    assert c.animation == "word_by_word"
    assert c.emphasis_words == []


def test_manifest_serialises_to_dict():
    m = EditManifest(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok", "youtube_shorts"],
        confidence=0.90,
        reasoning="High chat velocity spike at 12s.",
    )
    d = m.model_dump()
    assert d["confidence"] == 0.90
    assert "zooms" in d
