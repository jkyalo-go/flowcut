from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_workspace
from contracts.media import SubscribeAutoResponse, SubscribeItemResponse, SubscribeItemUpdate
from domain.media import SubscribeItem, TimelineItem
from domain.projects import Project
from services.subscribe_overlay_generator import generate_subscribe_overlays
from routes.titles import _build_timestamped_transcript
from routes import require_project

router = APIRouter()


@router.get("/{project_id}", response_model=SubscribeAutoResponse)
def get_subscribes(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    items = (
        db.query(SubscribeItem)
        .filter(SubscribeItem.project_id == project_id, SubscribeItem.workspace_id == workspace.id)
        .order_by(SubscribeItem.start_time)
        .all()
    )
    return SubscribeAutoResponse(items=[SubscribeItemResponse.model_validate(i) for i in items])


@router.post("/{project_id}/auto", response_model=SubscribeAutoResponse)
def auto_generate_subscribes(
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

    transcript_text, total_duration = _build_timestamped_transcript(timeline_items, workspace.id)
    if not transcript_text or total_duration <= 0:
        raise HTTPException(400, "No transcript available — process clips first")

    overlays = generate_subscribe_overlays(transcript_text, total_duration)

    # Replace existing subscribe items
    db.query(SubscribeItem).filter(
        SubscribeItem.project_id == project_id, SubscribeItem.workspace_id == workspace.id
    ).delete()

    new_items = []
    for o in overlays:
        item = SubscribeItem(
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

    return SubscribeAutoResponse(items=[SubscribeItemResponse.model_validate(i) for i in new_items])


@router.put("/{project_id}/items/{item_id}", response_model=SubscribeItemResponse)
def update_subscribe_item(
    project_id: str,
    item_id: str,
    body: SubscribeItemUpdate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    item = (
        db.query(SubscribeItem)
        .filter(
            SubscribeItem.id == item_id,
            SubscribeItem.project_id == project_id,
            SubscribeItem.workspace_id == workspace.id,
        )
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
def clear_subscribes(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    db.query(SubscribeItem).filter(
        SubscribeItem.project_id == project_id, SubscribeItem.workspace_id == workspace.id
    ).delete()
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/items/{item_id}")
def delete_subscribe_item(
    project_id: str,
    item_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    rows = (
        db.query(SubscribeItem)
        .filter(
            SubscribeItem.id == item_id,
            SubscribeItem.project_id == project_id,
            SubscribeItem.workspace_id == workspace.id,
        )
        .delete()
    )
    if rows == 0:
        raise HTTPException(404, "Subscribe item not found")
    db.commit()
    return {"ok": True}
