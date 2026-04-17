from __future__ import annotations
import json
from sqlalchemy.orm import Session
from services.ai_registry import registry
from services.sie.schemas import EditManifest

_SYSTEM_PROMPT = (
    "You are an expert video editor. Analyze the footage and produce a precise edit plan. "
    "Use the reasoning field to show your thinking — which moments are strongest, what pacing "
    "fits the creator's style, what platform constraints apply. Then fill all manifest fields. "
    "All timestamps must be within the footage duration."
)


def _build_user_prompt(
    footage_path: str,
    footage_duration_sec: float,
    moments: list[dict],
    style_profile: dict,
    episodic_context: list[dict],
) -> str:
    """Build the user prompt for the edit-planning LLM call.

    episodic_context is truncated to the last 3 items — ensures appended critique
    from run_reflection_loop is always included.
    """
    parts = [
        f"Footage: {footage_path} ({footage_duration_sec:.1f}s total)",
        f"Style profile: {json.dumps(style_profile)}",
        f"Detected moments: {json.dumps(moments)}",
    ]
    if episodic_context:
        parts.append(f"Past edits for reference: {json.dumps(episodic_context[-3:])}")
    parts.append("Produce the EditManifest. Aim for 15–60s output clip.")
    return "\n\n".join(parts)


def generate_edit_plan(
    footage_path: str,
    footage_duration_sec: float,
    moments: list[dict],
    style_profile: dict,
    episodic_context: list[dict],
    db: Session | None = None,
    workspace=None,
) -> EditManifest:
    """Single-pass Instructor call: reasoning + structured manifest in one LLM call.
    The EditManifest.reasoning field captures chain-of-thought without a second API call.
    Pass db + workspace for live calls; mock generate_edit_plan directly for unit tests."""
    if db is None or workspace is None:
        raise ValueError("db and workspace are required")
    user_prompt = _build_user_prompt(
        footage_path, footage_duration_sec, moments, style_profile, episodic_context,
    )
    return registry.run_structured_task(
        db=db,
        workspace=workspace,
        task_type="edit_planning",
        prompt_builder=lambda p, m: (_SYSTEM_PROMPT, user_prompt),
        response_model=EditManifest,
        max_retries=3,
    )
