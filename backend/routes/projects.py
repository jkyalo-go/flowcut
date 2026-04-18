import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from contracts.media import (
    AssetResponse,
    CaptionItemResponse,
    ClipResponse,
    MusicItemResponse,
    SubscribeItemResponse,
    TimelineItemResponse,
    TimestampItemResponse,
    TitleItemResponse,
    TrackerItemResponse,
    VolumeKeypoint,
)
from contracts.projects import ProjectCreate, ProjectMetadataUpdate, ProjectResponse
from database import get_db
from dependencies import get_current_workspace
from domain.media import (
    Asset,
    CaptionItem,
    Clip,
    MusicItem,
    SubscribeItem,
    TimelineItem,
    TimestampItem,
    TitleItem,
    TrackerItem,
)
from domain.platforms import CalendarSlot, PlatformConnection
from domain.projects import Project
from routes.music import _build_timeline_segments
from routes.platforms import PLATFORM_CAPABILITIES, _serialize_platform_surface
from routes.timeline import _resolve_item
from routes.trackers import _overlay_url
from services.ducker import compute_volume_envelope

router = APIRouter()


def _parse_json_field(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value)
    except Exception:
        return fallback
    return parsed


def _serialize_project(project: Project) -> dict:
    return {
        "id": project.id,
        "workspace_id": project.workspace_id,
        "name": project.name,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "render_path": project.render_path,
        "autonomy_mode": project.autonomy_mode.value if hasattr(project.autonomy_mode, "value") else project.autonomy_mode,
        "selected_title": project.selected_title,
        "video_description": project.video_description,
        "video_tags": _parse_json_field(project.video_tags, []),
        "video_category": project.video_category or "22",
        "video_visibility": project.video_visibility or "private",
        "selected_thumbnail_idx": project.selected_thumbnail_idx,
        "desc_system_prompt": project.desc_system_prompt or "",
        "thumbnail_urls": _parse_json_field(project.thumbnail_urls, []),
        "locked_thumbnail_indices": _parse_json_field(project.locked_thumbnail_indices, []),
        "thumbnail_text": project.thumbnail_text or "",
    }


def _serialize_slot(row: CalendarSlot) -> dict:
    return {
        "id": row.id,
        "platform": row.platform.value if hasattr(row.platform, "value") else str(row.platform),
        "project_id": row.project_id,
        "clip_id": row.clip_id,
        "render_variant": row.render_variant,
        "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "status": row.status,
        "publish_url": row.publish_url,
        "failure_reason": row.failure_reason,
        "retry_count": row.retry_count,
        "correlation_id": row.correlation_id,
        "metadata": _parse_json_field(row.metadata_json, {}),
    }


@router.post("", response_model=ProjectResponse)
def create_project(
    body: ProjectCreate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    if body.workspace_id != workspace.id:
        raise HTTPException(403, "Workspace mismatch")
    project = Project(
        workspace_id=workspace.id,
        name=body.name,
        intake_mode="upload",
        source_type="upload",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return db.query(Project).filter(Project.workspace_id == workspace.id).all()


@router.get("/{project_id}/workspace")
def get_project_workspace(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    clips = (
        db.query(Clip)
        .filter(Clip.project_id == project_id, Clip.workspace_id == workspace.id)
        .order_by(Clip.created_at.desc())
        .all()
    )
    timeline_items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id, TimelineItem.workspace_id == workspace.id)
        .order_by(TimelineItem.position)
        .all()
    )
    assets = (
        db.query(Asset)
        .filter(Asset.workspace_id == workspace.id)
        .order_by(Asset.created_at.desc())
        .all()
    )
    music_items = (
        db.query(MusicItem)
        .filter(MusicItem.project_id == project_id, MusicItem.workspace_id == workspace.id)
        .order_by(MusicItem.start_time)
        .all()
    )
    title_items = (
        db.query(TitleItem)
        .filter(TitleItem.project_id == project_id, TitleItem.workspace_id == workspace.id)
        .order_by(TitleItem.start_time)
        .all()
    )
    caption_items = (
        db.query(CaptionItem)
        .filter(CaptionItem.project_id == project_id, CaptionItem.workspace_id == workspace.id)
        .order_by(CaptionItem.start_time)
        .all()
    )
    timestamp_items = (
        db.query(TimestampItem)
        .filter(TimestampItem.project_id == project_id, TimestampItem.workspace_id == workspace.id)
        .order_by(TimestampItem.start_time)
        .all()
    )
    tracker_items = (
        db.query(TrackerItem)
        .filter(TrackerItem.project_id == project_id, TrackerItem.workspace_id == workspace.id)
        .order_by(TrackerItem.start_time)
        .all()
    )
    subscribe_items = (
        db.query(SubscribeItem)
        .filter(SubscribeItem.project_id == project_id, SubscribeItem.workspace_id == workspace.id)
        .order_by(SubscribeItem.start_time)
        .all()
    )
    slots = (
        db.query(CalendarSlot)
        .filter(CalendarSlot.project_id == project_id, CalendarSlot.workspace_id == workspace.id)
        .order_by(CalendarSlot.created_at.desc())
        .limit(20)
        .all()
    )
    platform_rows = db.query(PlatformConnection).filter(PlatformConnection.workspace_id == workspace.id).all()
    by_platform = {row.platform.value: row for row in platform_rows}
    segments, total_duration = _build_timeline_segments(timeline_items)
    envelope = compute_volume_envelope(segments, total_duration)

    return {
        "project": _serialize_project(project),
        "clips": [ClipResponse.model_validate(clip).model_dump() for clip in clips],
        "timeline": {
            "items": [TimelineItemResponse.model_validate(_resolve_item(item)).model_dump() for item in timeline_items],
        },
        "assets": [AssetResponse.model_validate(asset).model_dump() for asset in assets],
        "music": {
            "items": [MusicItemResponse.model_validate(item).model_dump() for item in music_items],
            "volume_envelope": [VolumeKeypoint(**point).model_dump() for point in envelope],
        },
        "overlays": {
            "titles": [TitleItemResponse.model_validate(item).model_dump() for item in title_items],
            "captions": [CaptionItemResponse.model_validate(item).model_dump() for item in caption_items],
            "timestamps": [TimestampItemResponse.model_validate(item).model_dump() for item in timestamp_items],
            "trackers": [
                TrackerItemResponse(
                    id=item.id,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    overlay_url=_overlay_url(item.overlay_path),
                ).model_dump()
                for item in tracker_items
            ],
            "subscribes": [SubscribeItemResponse.model_validate(item).model_dump() for item in subscribe_items],
        },
        "render": {
            "status": "done" if project.render_path else "idle",
            "has_render": bool(project.render_path),
            "render_path": project.render_path,
        },
        "publish": {
            "platforms": [
                _serialize_platform_surface(platform, capabilities, by_platform.get(platform))
                for platform, capabilities in PLATFORM_CAPABILITIES.items()
            ],
            "recent_slots": [_serialize_slot(slot) for slot in slots],
            "autonomy": {
                "autonomy_mode": project.autonomy_mode.value if hasattr(project.autonomy_mode, "value") else (project.autonomy_mode or workspace.autonomy_mode.value),
                "confidence_threshold": project.autonomy_confidence_threshold or workspace.autonomy_confidence_threshold,
            },
        },
    }


@router.put("/{project_id}/metadata")
def update_metadata(project_id: str, body: ProjectMetadataUpdate, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}")
def delete_project(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    db.delete(project)
    db.commit()
    return {"ok": True}
