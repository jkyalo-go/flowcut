from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_workspace
from contracts.media import TitleAutoResponse, TitleItemResponse, TitleItemUpdate
from domain.media import TimelineItem, TitleItem
from domain.projects import Project
from services.title_overlay_generator import generate_title_overlays
from routes import require_project

router = APIRouter()


def _build_timestamped_transcript(
    items: list[TimelineItem],
    workspace_id: str | None = None,
) -> tuple[str, float]:
    """Walk ordered timeline items and produce a timestamped transcript string."""
    parts = []
    cursor = 0.0
    seen_clip_ids: set[str] = set()
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

        # Attach the parent clip's transcript only on the FIRST sub-clip from that clip
        # to avoid repeating the same text for every speech segment
        transcript = ""
        if clip and clip.transcript and clip.id not in seen_clip_ids:
            transcript = clip.transcript
            seen_clip_ids.add(clip.id)

        if transcript:
            parts.append(f"[{cursor:.1f}s - {cursor + duration:.1f}s] {transcript}")
        cursor += duration

    return "\n".join(parts), cursor


@router.get("/{project_id}", response_model=TitleAutoResponse)
def get_titles(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    items = (
        db.query(TitleItem)
        .filter(TitleItem.project_id == project_id, TitleItem.workspace_id == workspace.id)
        .order_by(TitleItem.start_time)
        .all()
    )
    return TitleAutoResponse(items=[TitleItemResponse.model_validate(i) for i in items])


@router.post("/{project_id}/auto", response_model=TitleAutoResponse)
def auto_generate_titles(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    project = require_project(project_id, workspace.id, db)

    timeline_items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id, TimelineItem.workspace_id == workspace.id)
        .order_by(TimelineItem.position)
        .all()
    )

    transcript_text, total_duration = _build_timestamped_transcript(timeline_items, workspace.id)
    if not transcript_text or total_duration <= 0:
        raise HTTPException(400, "No transcript available — process clips first")

    overlays = generate_title_overlays(transcript_text, total_duration, project.workspace_id)

    # Replace existing titles
    db.query(TitleItem).filter(
        TitleItem.project_id == project_id, TitleItem.workspace_id == workspace.id
    ).delete()

    new_items = []
    for o in overlays:
        item = TitleItem(
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

    return TitleAutoResponse(items=[TitleItemResponse.model_validate(i) for i in new_items])


@router.put("/{project_id}/items/{item_id}", response_model=TitleItemResponse)
def update_title_item(
    project_id: str,
    item_id: str,
    body: TitleItemUpdate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    item = (
        db.query(TitleItem)
        .filter(
            TitleItem.id == item_id,
            TitleItem.project_id == project_id,
            TitleItem.workspace_id == workspace.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(404, "Title item not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return TitleItemResponse.model_validate(item)


@router.delete("/{project_id}")
def clear_titles(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    db.query(TitleItem).filter(
        TitleItem.project_id == project_id, TitleItem.workspace_id == workspace.id
    ).delete()
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/items/{item_id}")
def delete_title_item(
    project_id: str,
    item_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    rows = (
        db.query(TitleItem)
        .filter(
            TitleItem.id == item_id,
            TitleItem.project_id == project_id,
            TitleItem.workspace_id == workspace.id,
        )
        .delete()
    )
    if rows == 0:
        raise HTTPException(404, "Title item not found")
    db.commit()
    return {"ok": True}
