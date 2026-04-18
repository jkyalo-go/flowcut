from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from domain.shared import AIProvider, CredentialSource


class _Schema(BaseModel):
    answer: str
    score: float


def _make_workspace(policy: dict | None = None):
    import json
    ws = MagicMock()
    ws.id = "ws-test"
    ws.ai_policy = json.dumps(policy) if policy else None
    return ws


def test_run_structured_task_anthropic(db):
    """registry.run_structured_task routes to Anthropic and returns parsed schema."""
    from services.ai_registry import AIProviderRegistry
    reg = AIProviderRegistry()

    fake_result = _Schema(answer="yes", score=0.9)
    with patch.object(reg, "select_provider", return_value=(
        AIProvider.ANTHROPIC, "claude-sonnet-4-6", CredentialSource.PLATFORM, None
    )), patch.object(reg, "_run_instructor_anthropic", return_value=fake_result):
        ws = _make_workspace()
        result = reg.run_structured_task(
            db=db,
            workspace=ws,
            task_type="edit_planning",
            prompt_builder=lambda p, m: (None, "Analyze this footage."),
            response_model=_Schema,
        )
    assert result.answer == "yes"
    assert result.score == 0.9


def test_run_structured_task_openai(db):
    """registry.run_structured_task routes to OpenAI and returns parsed schema."""
    from services.ai_registry import AIProviderRegistry
    reg = AIProviderRegistry()

    fake_result = _Schema(answer="no", score=0.7)
    with patch.object(reg, "select_provider", return_value=(
        AIProvider.OPENAI, "gpt-4o", CredentialSource.BYOK, "sk-test"
    )), patch.object(reg, "_run_instructor_openai", return_value=fake_result):
        ws = _make_workspace()
        result = reg.run_structured_task(
            db=db,
            workspace=ws,
            task_type="edit_planning",
            prompt_builder=lambda p, m: (None, "Analyze this footage."),
            response_model=_Schema,
        )
    assert result.answer == "no"


def test_openai_added_to_provider_enum():
    """OPENAI is present in the AIProvider enum."""
    from domain.shared import AIProvider
    assert AIProvider.OPENAI.value == "openai"


def test_edit_planning_in_task_defaults():
    """edit_planning and style_critique have default providers."""
    from services.ai_registry import TASK_PROVIDER_DEFAULTS
    assert "edit_planning" in TASK_PROVIDER_DEFAULTS
    assert "style_critique" in TASK_PROVIDER_DEFAULTS
