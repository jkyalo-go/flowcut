from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from contracts.media import TimelineItemResponse, TimelineUpdate
from database import get_db
from dependencies import get_current_workspace
from domain.media import TimelineItem
from domain.projects import Project

router = APIRouter()


def _resolve_item(item: TimelineItem) -> TimelineItemResponse:
    from urllib.parse import quote

    if item.sub_clip_id and item.sub_clip:
        sub = item.sub_clip
        parent = sub.parent_clip
        source_path = parent.source_path if parent else ""
        playback_path = (parent.processed_path or parent.source_path) if parent else ""
        video_url = f"/api/fs/serve-video?path={quote(playback_path, safe='')}" if playback_path else ""
        start_time = sub.start_time
        end_time = sub.end_time
        duration = end_time - start_time
        clip_type = parent.clip_type.value if parent and parent.clip_type else None
        filename = source_path.split("/")[-1] if source_path else "Unknown"
        if clip_type == "broll":
            label = f"{filename} ({sub.label or 'moment'})"
        else:
            label = filename
    elif item.clip_id and item.clip:
        clip = item.clip
        source_path = clip.source_path
        playback_path = clip.processed_path or clip.source_path
        video_url = f"/api/fs/serve-video?path={quote(playback_path, safe='')}" if playback_path else ""
        start_time = 0
        end_time = clip.duration or 0
        duration = end_time
        label = source_path.split("/")[-1]
        clip_type = clip.clip_type.value if clip.clip_type else None
    else:
        video_url = ""
        start_time = 0
        end_time = 0
        duration = 0
        label = "Unknown"
        clip_type = None

    return TimelineItemResponse(
        id=item.id,
        clip_id=item.clip_id,
        sub_clip_id=item.sub_clip_id,
        position=item.position,
        video_url=video_url,
        duration=duration,
        start_time=start_time,
        end_time=end_time,
        label=label,
        clip_type=clip_type,
    )


@router.get("/{project_id}", response_model=list[TimelineItemResponse])
def get_timeline(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id, TimelineItem.workspace_id == workspace.id)
        .order_by(TimelineItem.position)
        .all()
    )
    return [_resolve_item(item) for item in items]


@router.put("/{project_id}", response_model=list[TimelineItemResponse])
def update_timeline(project_id: str, body: TimelineUpdate, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    # Delete existing timeline items
    db.query(TimelineItem).filter(TimelineItem.project_id == project_id, TimelineItem.workspace_id == workspace.id).delete()

    # Create new items
    new_items = []
    for entry in body.items:
        item = TimelineItem(
            workspace_id=workspace.id,
            project_id=project_id,
            clip_id=entry.clip_id,
            sub_clip_id=entry.sub_clip_id,
            position=entry.position,
        )
        db.add(item)
        new_items.append(item)

    db.commit()
    for item in new_items:
        db.refresh(item)
    return [_resolve_item(item) for item in new_items]


@router.delete("/{project_id}/items/{item_id}")
def remove_timeline_item(project_id: str, item_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    item = db.query(TimelineItem).filter(
        TimelineItem.id == item_id, TimelineItem.project_id == project_id, TimelineItem.workspace_id == workspace.id
    ).first()
    if not item:
        raise HTTPException(404, "Timeline item not found")
    db.delete(item)
    # Re-number remaining items
    remaining = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id, TimelineItem.workspace_id == workspace.id)
        .order_by(TimelineItem.position)
        .all()
    )
    for i, r in enumerate(remaining):
        r.position = i
    db.commit()
    return {"ok": True}
