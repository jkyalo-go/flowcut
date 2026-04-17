import math
import random
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from contracts.media import TrackerAutoResponse, TrackerItemResponse
from domain.media import TimelineItem, TrackerItem
from domain.projects import Project
from domain.shared import ClipType
from services.tracker_generator import generate_tracker_overlay
from config import PROCESSED_DIR

router = APIRouter()

TRACKER_DIR = PROCESSED_DIR.parent / "trackers"
SELECT_RATIO = 0.03


def _overlay_url(overlay_path: str) -> str:
    """Convert filesystem path to a serveable URL."""
    # overlay_path is under backend/static/trackers/...
    # /static mount serves from backend/static/
    rel = Path(overlay_path).relative_to(PROCESSED_DIR.parent)
    return f"/static/{rel}"


@router.get("/{project_id}", response_model=TrackerAutoResponse)
def get_trackers(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    items = (
        db.query(TrackerItem)
        .filter(TrackerItem.project_id == project_id)
        .order_by(TrackerItem.start_time)
        .all()
    )
    return TrackerAutoResponse(
        items=[
            TrackerItemResponse(
                id=i.id,
                start_time=i.start_time,
                end_time=i.end_time,
                overlay_url=_overlay_url(i.overlay_path),
            )
            for i in items
        ]
    )


@router.post("/{project_id}/auto", response_model=TrackerAutoResponse)
async def auto_generate_trackers(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    timeline_items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id)
        .order_by(TimelineItem.position)
        .all()
    )

    # Walk timeline to compute each item's timeline start/end and identify b-roll
    broll_entries = []  # (timeline_start, timeline_end, source_path, source_start, source_end)
    cursor = 0.0

    for item in timeline_items:
        if item.sub_clip_id and item.sub_clip:
            sub = item.sub_clip
            clip = sub.parent_clip
            if not clip:
                continue
            duration = sub.end_time - sub.start_time
            source_path = clip.source_path
            source_start = sub.start_time
            source_end = sub.end_time
            clip_type = clip.clip_type
        elif item.clip_id and item.clip:
            clip = item.clip
            duration = clip.duration or 0
            source_path = clip.source_path
            source_start = 0
            source_end = duration
            clip_type = clip.clip_type
        else:
            continue

        if duration < 0.034:
            continue

        timeline_start = cursor
        timeline_end = cursor + duration
        cursor += duration

        if clip_type == ClipType.BROLL:
            broll_entries.append((timeline_start, timeline_end, source_path, source_start, source_end))

    if not broll_entries:
        raise HTTPException(400, "No b-roll clips on the timeline")

    # Select 3% of b-roll clips (at least 1)
    count = max(1, math.ceil(len(broll_entries) * SELECT_RATIO))
    selected = random.sample(broll_entries, min(count, len(broll_entries)))

    # Clear existing trackers
    db.query(TrackerItem).filter(TrackerItem.project_id == project_id).delete()
    proj_dir = TRACKER_DIR / str(project_id)
    if proj_dir.exists():
        shutil.rmtree(proj_dir)
    proj_dir.mkdir(parents=True, exist_ok=True)

    db.commit()

    new_items = []
    for idx, (tl_start, tl_end, src_path, src_start, src_end) in enumerate(selected):
        out_path = str(proj_dir / f"tracker_{idx}.webm")
        await generate_tracker_overlay(
            source_path=src_path,
            start_time=src_start,
            end_time=src_end,
            output_path=out_path,
        )
        item = TrackerItem(
            project_id=project_id,
            start_time=tl_start,
            end_time=tl_end,
            overlay_path=out_path,
        )
        db.add(item)
        new_items.append(item)

    db.commit()
    for item in new_items:
        db.refresh(item)

    return TrackerAutoResponse(
        items=[
            TrackerItemResponse(
                id=i.id,
                start_time=i.start_time,
                end_time=i.end_time,
                overlay_url=_overlay_url(i.overlay_path),
            )
            for i in new_items
        ]
    )


@router.delete("/{project_id}")
def clear_trackers(project_id: str, db: Session = Depends(get_db)):
    db.query(TrackerItem).filter(TrackerItem.project_id == project_id).delete()
    db.commit()

    proj_dir = TRACKER_DIR / str(project_id)
    if proj_dir.exists():
        shutil.rmtree(proj_dir)

    return {"ok": True}
