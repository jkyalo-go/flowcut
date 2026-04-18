from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from contracts.media import CaptionAutoResponse, CaptionItemResponse, CaptionItemUpdate
from database import get_db
from dependencies import get_current_workspace
from domain.media import CaptionItem, TimelineItem
from routes import require_project

router = APIRouter()

WORDS_PER_PHRASE = 5


def _split_into_phrases(text: str, words_per_phrase: int = WORDS_PER_PHRASE) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + words_per_phrase]) for i in range(0, len(words), words_per_phrase)]


@router.get("/{project_id}", response_model=CaptionAutoResponse)
def get_captions(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    items = (
        db.query(CaptionItem)
        .filter(CaptionItem.project_id == project_id, CaptionItem.workspace_id == workspace.id)
        .order_by(CaptionItem.start_time)
        .all()
    )
    return CaptionAutoResponse(items=[CaptionItemResponse.model_validate(i) for i in items])


@router.post("/{project_id}/auto", response_model=CaptionAutoResponse)
def auto_generate_captions(
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

    cursor = 0.0
    captions = []
    for item in timeline_items:
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

        clip_type = clip.clip_type.value if clip and clip.clip_type else None
        transcript = clip.transcript if clip else None

        if clip_type == "talking" and transcript:
            phrases = _split_into_phrases(transcript)
            if phrases:
                phrase_duration = duration / len(phrases)
                for i, phrase in enumerate(phrases):
                    start = cursor + i * phrase_duration
                    captions.append({
                        "text": phrase,
                        "start_time": round(start, 2),
                        "end_time": round(start + phrase_duration, 2),
                    })
        cursor += duration

    if not captions:
        raise HTTPException(400, "No talking clips with transcripts found")

    db.query(CaptionItem).filter(
        CaptionItem.project_id == project_id, CaptionItem.workspace_id == workspace.id
    ).delete()

    new_items = []
    for c in captions:
        item = CaptionItem(
            workspace_id=workspace.id,
            project_id=project_id,
            text=c["text"],
            start_time=c["start_time"],
            end_time=c["end_time"],
        )
        db.add(item)
        new_items.append(item)

    db.commit()
    for item in new_items:
        db.refresh(item)

    return CaptionAutoResponse(items=[CaptionItemResponse.model_validate(i) for i in new_items])


@router.put("/{project_id}/items/{item_id}", response_model=CaptionItemResponse)
def update_caption_item(
    project_id: str,
    item_id: str,
    body: CaptionItemUpdate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    item = db.query(CaptionItem).filter(
        CaptionItem.id == item_id,
        CaptionItem.project_id == project_id,
        CaptionItem.workspace_id == workspace.id,
    ).first()
    if not item:
        raise HTTPException(404, "Caption item not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return CaptionItemResponse.model_validate(item)


@router.delete("/{project_id}")
def clear_captions(
    project_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    db.query(CaptionItem).filter(
        CaptionItem.project_id == project_id, CaptionItem.workspace_id == workspace.id
    ).delete()
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/items/{item_id}")
def delete_caption_item(
    project_id: str,
    item_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    require_project(project_id, workspace.id, db)
    rows = db.query(CaptionItem).filter(
        CaptionItem.id == item_id,
        CaptionItem.project_id == project_id,
        CaptionItem.workspace_id == workspace.id,
    ).delete()
    if rows == 0:
        raise HTTPException(404, "Caption item not found")
    db.commit()
    return {"ok": True}
