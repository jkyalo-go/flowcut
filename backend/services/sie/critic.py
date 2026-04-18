from __future__ import annotations

import json

from sqlalchemy.orm import Session

from services.ai_registry import registry
from services.sie import planner as _planner
from services.sie.schemas import EditManifest


def critique_manifest(
    manifest: EditManifest,
    style_profile: dict,
    db: Session | None = None,
    workspace=None,
) -> str:
    """Returns a plain-text critique of the manifest. Empty string if no issues found.
    Routes through registry so provider is workspace-configurable (default: Anthropic)."""
    if db is None or workspace is None:
        raise ValueError("db and workspace are required for critique_manifest")
    system = (
        "You are a senior video editor reviewing an AI-generated edit plan. "
        "Be concise and specific. If the plan looks good, say 'LGTM'. "
        "Otherwise list specific issues: weak hook, pacing problems, style mismatches."
    )
    user_content = (
        f"Style profile: {json.dumps(style_profile)}\n\n"
        f"Edit manifest:\n{manifest.model_dump_json(indent=2)}\n\n"
        "Critique this plan."
    )

    text = registry.run_text_task(
        db=db,
        workspace=workspace,
        task_type="style_critique",
        prompt_builder=lambda p, m: (system, user_content),
        parser=lambda t: t.strip(),
    )

    return "" if text.upper().startswith("LGTM") else text


def run_reflection_loop(
    initial_manifest: EditManifest,
    footage_path: str,
    footage_duration_sec: float,
    moments: list[dict],
    style_profile: dict,
    episodic_context: list[dict],
    min_confidence: float = 0.70,
    max_iterations: int = 1,
    db: Session | None = None,
    workspace=None,
) -> EditManifest:
    """Run at most max_iterations refinement cycles.
    Returns the refined manifest if confidence improves, otherwise the original."""
    manifest = initial_manifest
    for _ in range(max_iterations):
        if manifest.confidence >= min_confidence:
            break
        critique = critique_manifest(manifest, style_profile, db, workspace)
        if not critique:
            break
        refined_context = episodic_context + [{"critique": critique}]
        candidate = _planner.generate_edit_plan(
            footage_path=footage_path,
            footage_duration_sec=footage_duration_sec,
            moments=moments,
            style_profile={**style_profile, "critique_to_address": critique},
            episodic_context=refined_context,
            db=db,
            workspace=workspace,
        )
        if candidate.confidence > manifest.confidence:
            manifest = candidate
    return manifest
