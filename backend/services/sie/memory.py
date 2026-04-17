from __future__ import annotations
import logging

logger = logging.getLogger(__name__)
_mem0 = None


def _get_mem0():
    global _mem0
    if _mem0 is None:
        from mem0 import Memory
        _mem0 = Memory()
    return _mem0


def store_edit_episode(mem0_user_id: str, clip_id: str, manifest_summary: str, critique: str | None, action: str) -> None:
    """Store a single edit episode in Mem0 episodic memory. Non-fatal on Mem0 failure."""
    text = f"Clip {clip_id}: {action}. Manifest: {manifest_summary}."
    if critique:
        text += f" Critique: {critique}"
    try:
        _get_mem0().add(text, user_id=mem0_user_id)
    except Exception:
        logger.warning("Mem0 store_edit_episode failed — continuing without episodic storage")


def retrieve_episodic_context(mem0_user_id: str, query: str, limit: int = 5) -> list[dict]:
    """Retrieve relevant past edit episodes. Returns [] if Mem0 is unavailable."""
    try:
        results = _get_mem0().search(query, user_id=mem0_user_id, limit=limit)
        return [{"memory": r["memory"], "score": r.get("score", 0)} for r in results]
    except Exception:
        logger.warning("Mem0 retrieve_episodic_context failed — returning empty context")
        return []
