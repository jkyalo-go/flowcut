from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_workspace
from contracts.media import TimestampAutoResponse, TimestampItemResponse, TimestampItemUpdate
from domain.media import TimelineItem, TimestampItem
from services.timestamp_generator import generate_timestamps
from routes.settings import _get_setting
from routes import require_project

router = APIRouter()


def _build_datetime_transcript(items: list[TimelineItem], tz: ZoneInfo) -> tuple[str, float]:
    """Walk ordered timeline items, collapsing consecutive sub-clips from the same source clip."""
    parts = []
    cursor = 0.0
    last_clip_id = None
    group_start = 0.0

    for item in items:
        if item.sub_clip_id and item.sub_clip:
            sub = item.sub_clip
            duration = sub.end_time - sub.start_time
            clip = sub.parent_clip
            clip_id = clip.id if clip else None
        elif item.clip_id and item.clip:
            clip = item.clip
            duration = clip.duration or 0
            clip_id = clip.id
        else:
            continue

        if duration < 0.034:
            continue

        # If same clip as previous, just extend the cursor
        if clip_id == last_clip_id and last_clip_id is not None:
            cursor += duration
            continue

        # New clip — emit a line
        recorded_at = clip.recorded_at if clip else None
        if recorded_at:
            utc_dt = recorded_at.replace(tzinfo=timezone.utc)
            local_dt = utc_dt.astimezone(tz)
            datetime_str = local_dt.strftime("%A %B %d, %Y %I:%M %p")
        else:
            datetime_str = "unknown"

        clip_type = clip.clip_type.value if clip and clip.clip_type else "unknown"
        line = f"[{cursor:.1f}s] (recorded: {datetime_str}) [{clip_type}]"
        parts.append(line)

        last_clip_id = clip_id
        cursor += duration

    return "\n".join(parts), cursor


@router.get("/{project_id}", response_model=TimestampAutoResponse)
def get_timestamps(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    items = (
        db.query(TimestampItem)
        .filter(TimestampItem.project_id == project_id, TimestampItem.workspace_id == workspace.id)
        .order_by(TimestampItem.start_time)
        .all()
    )
    return TimestampAutoResponse(items=[TimestampItemResponse.model_validate(i) for i in items])


@router.post("/{project_id}/auto", response_model=TimestampAutoResponse)
def auto_generate_timestamps(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)

    timeline_items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id, TimelineItem.workspace_id == workspace.id)
        .order_by(TimelineItem.position)
        .all()
    )

    tz_name = _get_setting(db, "timezone", workspace.id)
    tz = ZoneInfo(tz_name)
    transcript_text, total_duration = _build_datetime_transcript(timeline_items, tz)
    if not transcript_text or total_duration <= 0:
        raise HTTPException(400, "No clips available — process clips first")

    overlays = generate_timestamps(transcript_text, total_duration)

    # Replace existing timestamps
    db.query(TimestampItem).filter(
        TimestampItem.project_id == project_id, TimestampItem.workspace_id == workspace.id
    ).delete()

    new_items = []
    for o in overlays:
        item = TimestampItem(
            workspace_id=workspace.id,
            project_id=project_id,
            text=o["text"],
            start_time=o["start_time"],
            end_time=o["end_time"],
        )
        db.add(item)
        new_items.append(item)

    db.commit()
    for item in new_items:
        db.refresh(item)

    return TimestampAutoResponse(items=[TimestampItemResponse.model_validate(i) for i in new_items])


@router.put("/{project_id}/items/{item_id}", response_model=TimestampItemResponse)
def update_timestamp_item(
    project_id: str,
    item_id: str,
    body: TimestampItemUpdate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    item = (
        db.query(TimestampItem)
        .filter(
            TimestampItem.id == item_id,
            TimestampItem.project_id == project_id,
            TimestampItem.workspace_id == workspace.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(404, "Timestamp item not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return TimestampItemResponse.model_validate(item)


@router.delete("/{project_id}")
def clear_timestamps(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    db.query(TimestampItem).filter(
        TimestampItem.project_id == project_id, TimestampItem.workspace_id == workspace.id
    ).delete()
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/items/{item_id}")
def delete_timestamp_item(
    project_id: str,
    item_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    rows = (
        db.query(TimestampItem)
        .filter(
            TimestampItem.id == item_id,
            TimestampItem.project_id == project_id,
            TimestampItem.workspace_id == workspace.id,
        )
        .delete()
    )
    if rows == 0:
        raise HTTPException(404, "Timestamp item not found")
    db.commit()
    return {"ok": True}
