from __future__ import annotations
from typing import TypedDict, Annotated, List, Optional, Any
import operator
from langgraph.graph import StateGraph, END
from services.sie.schemas import EditManifest
from services.sie import workers, planner, critic, gates, memory
from database import SessionLocal


class SIEState(TypedDict):
    footage_id: str
    workspace_id: str
    profile_id: str
    video_path: str
    gcs_uri: Optional[str]
    footage_duration_sec: float
    style_doc: dict
    dimension_locks: dict
    mem0_user_id: Optional[str]
    scenes: List[dict]
    transcript: dict
    visual_moments: List[dict]
    ranked_moments: List[dict]
    episodic_context: List[dict]
    edit_manifest: Optional[EditManifest]
    gate_passed: bool
    gate_error: Optional[str]
    errors: Annotated[List[str], operator.add]


async def _analysis_node(state: SIEState) -> dict:
    result = await workers.run_all_workers(state["video_path"], state.get("gcs_uri"))
    return {
        "scenes": result["scenes"],
        "transcript": result["transcript"],
        "visual_moments": result["visual_moments"],
    }


async def _synthesis_node(state: SIEState) -> dict:
    visual = state.get("visual_moments", [])
    scenes = state.get("scenes", [])

    if visual:
        moments = sorted(visual, key=lambda m: m.get("engagement_score", 0), reverse=True)
    elif scenes:
        moments = [
            {"start_sec": s["start_sec"], "end_sec": s["end_sec"],
             "score": 0.6, "type": "scene", "sentiment": "neutral"}
            for s in scenes
        ]
    else:
        dur = state["footage_duration_sec"]
        moments = [
            {"start_sec": i * dur / 3, "end_sec": min((i + 1) * dur / 3, dur),
             "score": 0.5, "type": "segment", "sentiment": "neutral"}
            for i in range(3)
        ]

    episodic = []
    if state.get("mem0_user_id"):
        query = f"footage type for workspace {state['workspace_id']}"
        episodic = memory.retrieve_episodic_context(state["mem0_user_id"], query)

    return {"ranked_moments": moments[:10], "episodic_context": episodic}


async def _planning_node(state: SIEState) -> dict:
    from domain.identity import Workspace
    db = None
    try:
        db = SessionLocal()
        workspace = db.query(Workspace).filter(Workspace.id == state["workspace_id"]).first()
        if not workspace:
            return {"errors": [f"workspace {state['workspace_id']} not found"], "edit_manifest": None}
        manifest = planner.generate_edit_plan(
            footage_path=state["video_path"],
            footage_duration_sec=state["footage_duration_sec"],
            moments=state["ranked_moments"],
            style_profile=state["style_doc"],
            episodic_context=state["episodic_context"],
            db=db,
            workspace=workspace,
        )
        manifest = critic.run_reflection_loop(
            initial_manifest=manifest,
            footage_path=state["video_path"],
            footage_duration_sec=state["footage_duration_sec"],
            moments=state["ranked_moments"],
            style_profile=state["style_doc"],
            episodic_context=state["episodic_context"],
            db=db,
            workspace=workspace,
        )
        return {"edit_manifest": manifest}
    except Exception as e:
        return {"errors": [f"planning failed: {e}"], "edit_manifest": None}
    finally:
        if db is not None:
            db.close()


def _gate_node(state: SIEState) -> dict:
    if not state.get("edit_manifest"):
        return {"gate_passed": False, "gate_error": "no manifest produced"}
    try:
        gates.run_quality_gates(
            manifest=state["edit_manifest"],
            footage_duration_sec=state["footage_duration_sec"],
            style_profile=state["style_doc"],
        )
        return {"gate_passed": True, "gate_error": None}
    except gates.GateFailure as e:
        return {"gate_passed": False, "gate_error": str(e)}


def _should_continue(state: SIEState) -> str:
    return "gate" if state.get("edit_manifest") else END


def build_sie_graph() -> StateGraph:
    g = StateGraph(SIEState)
    g.add_node("analysis", _analysis_node)
    g.add_node("synthesis", _synthesis_node)
    g.add_node("planning", _planning_node)
    g.add_node("gate", _gate_node)

    g.set_entry_point("analysis")
    g.add_edge("analysis", "synthesis")
    g.add_edge("synthesis", "planning")
    g.add_conditional_edges("planning", _should_continue, {"gate": "gate", END: END})
    g.add_edge("gate", END)

    return g.compile()


_compiled_graph = None


def get_sie_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_sie_graph()
    return _compiled_graph


async def run_sie_pipeline(
    footage_id: str,
    workspace_id: str,
    profile_id: str,
    video_path: str,
    footage_duration_sec: float,
    style_doc: dict,
    dimension_locks: dict,
    gcs_uri: str | None = None,
    mem0_user_id: str | None = None,
) -> SIEState:
    graph = get_sie_graph()
    initial_state: SIEState = {
        "footage_id": footage_id,
        "workspace_id": workspace_id,
        "profile_id": profile_id,
        "video_path": video_path,
        "gcs_uri": gcs_uri,
        "footage_duration_sec": footage_duration_sec,
        "style_doc": style_doc,
        "dimension_locks": dimension_locks,
        "mem0_user_id": mem0_user_id,
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
    return await graph.ainvoke(initial_state)
