from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from contracts.media import SubscribeAutoResponse, SubscribeItemResponse, SubscribeItemUpdate
from domain.media import SubscribeItem, TimelineItem
from domain.projects import Project
from services.subscribe_overlay_generator import generate_subscribe_overlays
from routes.titles import _build_timestamped_transcript

router = APIRouter()


@router.get("/{project_id}", response_model=SubscribeAutoResponse)
def get_subscribes(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    items = (
        db.query(SubscribeItem)
        .filter(SubscribeItem.project_id == project_id)
        .order_by(SubscribeItem.start_time)
        .all()
    )
    return SubscribeAutoResponse(items=[SubscribeItemResponse.model_validate(i) for i in items])


@router.post("/{project_id}/auto", response_model=SubscribeAutoResponse)
def auto_generate_subscribes(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    timeline_items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id)
        .order_by(TimelineItem.position)
        .all()
    )

    transcript_text, total_duration = _build_timestamped_transcript(timeline_items)
    if not transcript_text or total_duration <= 0:
        raise HTTPException(400, "No transcript available — process clips first")

    overlays = generate_subscribe_overlays(transcript_text, total_duration)

    # Replace existing subscribe items
    db.query(SubscribeItem).filter(SubscribeItem.project_id == project_id).delete()

    new_items = []
    for o in overlays:
        item = SubscribeItem(
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

    return SubscribeAutoResponse(items=[SubscribeItemResponse.model_validate(i) for i in new_items])


@router.put("/{project_id}/items/{item_id}", response_model=SubscribeItemResponse)
def update_subscribe_item(
    project_id: str, item_id: str, body: SubscribeItemUpdate, db: Session = Depends(get_db)
):
    item = (
        db.query(SubscribeItem)
        .filter(SubscribeItem.id == item_id, SubscribeItem.project_id == project_id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Subscribe item not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return SubscribeItemResponse.model_validate(item)


@router.delete("/{project_id}")
def clear_subscribes(project_id: str, db: Session = Depends(get_db)):
    db.query(SubscribeItem).filter(SubscribeItem.project_id == project_id).delete()
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/items/{item_id}")
def delete_subscribe_item(project_id: str, item_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(SubscribeItem)
        .filter(SubscribeItem.id == item_id, SubscribeItem.project_id == project_id)
        .delete()
    )
    if rows == 0:
        raise HTTPException(404, "Subscribe item not found")
    db.commit()
    return {"ok": True}
