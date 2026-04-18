import asyncio
from unittest.mock import MagicMock, patch


def _make_state(**overrides):
    base = {
        "footage_id": "f1",
        "workspace_id": "ws-1",
        "profile_id": "p1",
        "video_path": "/tmp/test.mp4",
        "gcs_uri": None,
        "footage_duration_sec": 60.0,
        "style_doc": {"genre": "general"},
        "dimension_locks": {},
        "mem0_user_id": None,
        "scenes": [],
        "transcript": {},
        "visual_moments": [],
        "ranked_moments": [],
        "episodic_context": [],
        "edit_manifest": None,
        "gate_passed": False,
        "gate_error": None,
        "errors": [],
    }
    base.update(overrides)
    return base


def test_synthesis_falls_back_to_evenly_spaced_when_no_visual():
    """_synthesis_node uses evenly-spaced segments when both visual and scenes are empty."""
    from services.sie.graph import _synthesis_node
    state = _make_state(footage_duration_sec=90.0)
    with patch("services.sie.graph.memory.retrieve_episodic_context", return_value=[]):
        result = asyncio.run(_synthesis_node(state))
    assert len(result["ranked_moments"]) == 3
    assert result["ranked_moments"][0]["type"] == "segment"


def test_gate_node_passes_when_manifest_valid():
    from services.sie.graph import _gate_node
    from services.sie.schemas import EditManifest, TrimAction
    manifest = EditManifest(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok"],
        confidence=0.85,
        reasoning="Good hook.",
    )
    state = _make_state(edit_manifest=manifest, footage_duration_sec=60.0)
    with patch("services.sie.graph.gates.run_quality_gates"):
        result = _gate_node(state)
    assert result["gate_passed"] is True
    assert result["gate_error"] is None


def test_gate_node_fails_when_no_manifest():
    from services.sie.graph import _gate_node
    state = _make_state(edit_manifest=None)
    result = _gate_node(state)
    assert result["gate_passed"] is False
    assert "no manifest" in result["gate_error"]


def test_planning_node_records_error_when_workspace_missing():
    """_planning_node returns error state when workspace_id lookup fails."""
    from services.sie.graph import _planning_node
    state = _make_state(workspace_id="nonexistent-ws")
    with patch("services.sie.graph.SessionLocal") as mock_sl:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_sl.return_value = mock_db
        result = asyncio.run(_planning_node(state))
    assert result["edit_manifest"] is None
    assert any("not found" in e for e in result["errors"])
