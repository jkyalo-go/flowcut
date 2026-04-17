import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def test_re_plan_clip_no_clip_is_noop():
    """re_plan_clip with a missing clip ID does nothing (no crash)."""
    import asyncio
    from unittest.mock import patch, MagicMock
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("services.sie.re_planner.SessionLocal", return_value=mock_db):
        asyncio.run(__import__("services.sie.re_planner", fromlist=["re_plan_clip"]).re_plan_clip("missing-id", []))


def test_re_plan_clip_updates_status():
    """re_plan_clip sets clip.status = draft after corrections applied."""
    import asyncio
    from unittest.mock import patch, MagicMock

    mock_clip = MagicMock()
    mock_clip.id = "clip-1"
    mock_clip.profile_id = None
    mock_clip.status = "rejected"
    mock_clip.review_corrections = None

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_clip

    with patch("services.sie.re_planner.SessionLocal", return_value=mock_db):
        with patch("services.sie.re_planner.json.loads", return_value={}):
            asyncio.run(__import__("services.sie.re_planner", fromlist=["re_plan_clip"]).re_plan_clip(
                "clip-1", [{"instruction": "make intro shorter"}]
            ))

    assert mock_clip.status == "draft"
