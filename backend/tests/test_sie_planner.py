import pytest
from unittest.mock import patch, MagicMock
from services.sie.schemas import EditManifest, TrimAction


def _fake_manifest():
    return EditManifest(
        trim=TrimAction(start_sec=5.0, end_sec=35.0),
        platform_targets=["tiktok"],
        confidence=0.87,
        reasoning="Strong hook at 5s. Chat velocity spike at 12s suggests cut point.",
    )


def _make_workspace():
    ws = MagicMock()
    ws.id = "ws-test"
    ws.ai_policy = None
    return ws


def test_planner_returns_edit_manifest(db):
    """generate_edit_plan routes through run_structured_task and returns EditManifest."""
    ws = _make_workspace()
    from services.sie.planner import generate_edit_plan
    from services.ai_registry import AIProviderRegistry
    from domain.shared import AIProvider, CredentialSource

    with patch.object(AIProviderRegistry, "run_structured_task", return_value=_fake_manifest()):
        result = generate_edit_plan(
            footage_path="/tmp/test.mp4",
            footage_duration_sec=60.0,
            moments=[{"start_sec": 5.0, "end_sec": 35.0, "score": 0.9}],
            style_profile={"max_cuts_per_min": 15},
            episodic_context=[],
            db=db,
            workspace=ws,
        )
    assert isinstance(result, EditManifest)
    assert result.confidence == 0.87


def test_planner_includes_style_profile_in_prompt(db):
    """Style profile appears in the user prompt passed to run_structured_task."""
    ws = _make_workspace()
    from services.sie.planner import generate_edit_plan
    from services.ai_registry import AIProviderRegistry

    captured = {}
    def capture_call(db, workspace, task_type, prompt_builder, response_model, **kwargs):
        _, user_prompt = prompt_builder(None, None)
        captured["user_prompt"] = user_prompt
        return _fake_manifest()

    with patch.object(AIProviderRegistry, "run_structured_task", side_effect=capture_call):
        generate_edit_plan(
            footage_path="/tmp/test.mp4",
            footage_duration_sec=60.0,
            moments=[],
            style_profile={"pacing": "fast", "caption_style": "word_by_word"},
            episodic_context=[],
            db=db,
            workspace=ws,
        )
    assert "pacing" in captured["user_prompt"]
    assert "word_by_word" in captured["user_prompt"]


def test_critic_triggers_one_refinement_when_confidence_low(monkeypatch, db):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    low_conf_manifest = EditManifest(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok"],
        confidence=0.45,  # below threshold
        reasoning="Generic clip.",
    )
    high_conf_manifest = EditManifest(
        trim=TrimAction(start_sec=5.0, end_sec=35.0),
        platform_targets=["tiktok"],
        confidence=0.88,
        reasoning="Refined: strong hook at 5s.",
    )
    from services.ai_registry import registry as _registry
    import types
    _ws = types.SimpleNamespace(id="ws-test", ai_policy=None)
    with patch.object(_registry, "run_text_task", return_value="Hook is weak. Prefer start at 5s."), \
         patch.object(_registry, "run_structured_task", return_value=high_conf_manifest):
        from services.sie.critic import run_reflection_loop
        result = run_reflection_loop(
            initial_manifest=low_conf_manifest,
            footage_path="/tmp/test.mp4",
            footage_duration_sec=60.0,
            moments=[],
            style_profile={},
            episodic_context=[],
            min_confidence=0.70,
            db=db,
            workspace=_ws,
        )
    assert result.confidence >= 0.70  # at most 1 retry, refined manifest returned
