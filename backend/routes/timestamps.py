from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import TimestampItem, TimelineItem, Project
from schemas import TimestampItemResponse, TimestampItemUpdate, TimestampAutoResponse
from services.timestamp_generator import generate_timestamps
from routes.settings import _get_setting

router = APIRouter()


def _build_datetime_transcript(items: list[TimelineItem], tz: ZoneInfo) -> tuple[str, float]:
    """Walk ordered timeline items and produce a transcript with both timeline positions and recording datetimes."""
    parts = []
    cursor = 0.0
    for item in items:
        if item.sub_clip_id and item.sub_clip:
            sub = item.sub_clip
            duration = sub.end_time - sub.start_time
            clip = sub.parent_clip
        elif item.clip_id and item.clip:
            clip = item.clip
            duration = clip.duration or 0
        else:
            continue

        if duration < 0.034:
            continue

        recorded_at = clip.recorded_at if clip else None
        transcript = clip.transcript if clip else None

        if recorded_at:
            # recorded_at is UTC — convert to user's local timezone
            utc_dt = recorded_at.replace(tzinfo=timezone.utc)
            local_dt = utc_dt.astimezone(tz)
            datetime_str = local_dt.strftime("%A %B %d, %Y %I:%M %p")
        else:
            datetime_str = "unknown"

        line = f"[{cursor:.1f}s - {cursor + duration:.1f}s] (recorded: {datetime_str})"
        if transcript:
            line += f" {transcript}"
        parts.append(line)

        cursor += duration

    return "\n".join(parts), cursor


@router.get("/{project_id}", response_model=TimestampAutoResponse)
def get_timestamps(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    items = (
        db.query(TimestampItem)
        .filter(TimestampItem.project_id == project_id)
        .order_by(TimestampItem.start_time)
        .all()
    )
    return TimestampAutoResponse(items=[TimestampItemResponse.model_validate(i) for i in items])


@router.post("/{project_id}/auto", response_model=TimestampAutoResponse)
def auto_generate_timestamps(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    timeline_items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id)
        .order_by(TimelineItem.position)
        .all()
    )

    tz_name = _get_setting(db, "timezone")
    tz = ZoneInfo(tz_name)
    transcript_text, total_duration = _build_datetime_transcript(timeline_items, tz)
    if not transcript_text or total_duration <= 0:
        raise HTTPException(400, "No clips available — process clips first")

    overlays = generate_timestamps(transcript_text, total_duration)

    # Replace existing timestamps
    db.query(TimestampItem).filter(TimestampItem.project_id == project_id).delete()

    new_items = []
    for o in overlays:
        item = TimestampItem(
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
    project_id: int, item_id: int, body: TimestampItemUpdate, db: Session = Depends(get_db)
):
    item = (
        db.query(TimestampItem)
        .filter(TimestampItem.id == item_id, TimestampItem.project_id == project_id)
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
def clear_timestamps(project_id: int, db: Session = Depends(get_db)):
    db.query(TimestampItem).filter(TimestampItem.project_id == project_id).delete()
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/items/{item_id}")
def delete_timestamp_item(project_id: int, item_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(TimestampItem)
        .filter(TimestampItem.id == item_id, TimestampItem.project_id == project_id)
        .delete()
    )
    if rows == 0:
        raise HTTPException(404, "Timestamp item not found")
    db.commit()
    return {"ok": True}
