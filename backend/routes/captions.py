from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from contracts.media import CaptionAutoResponse, CaptionItemResponse, CaptionItemUpdate
from domain.media import CaptionItem, TimelineItem
from domain.projects import Project

router = APIRouter()

WORDS_PER_PHRASE = 5


def _split_into_phrases(text: str, words_per_phrase: int = WORDS_PER_PHRASE) -> list[str]:
    """Split text into short phrases of approximately words_per_phrase words."""
    words = text.split()
    phrases = []
    for i in range(0, len(words), words_per_phrase):
        phrase = " ".join(words[i:i + words_per_phrase])
        phrases.append(phrase)
    return phrases


@router.get("/{project_id}", response_model=CaptionAutoResponse)
def get_captions(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    items = (
        db.query(CaptionItem)
        .filter(CaptionItem.project_id == project_id)
        .order_by(CaptionItem.start_time)
        .all()
    )
    return CaptionAutoResponse(items=[CaptionItemResponse.model_validate(i) for i in items])


@router.post("/{project_id}/auto", response_model=CaptionAutoResponse)
def auto_generate_captions(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    timeline_items = (
        db.query(TimelineItem)
        .filter(TimelineItem.project_id == project_id)
        .order_by(TimelineItem.position)
        .all()
    )

    # Walk timeline and generate captions for talking clips
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
                    end = start + phrase_duration
                    captions.append({
                        "text": phrase,
                        "start_time": round(start, 2),
                        "end_time": round(end, 2),
                    })

        cursor += duration

    if not captions:
        raise HTTPException(400, "No talking clips with transcripts found")

    # Replace existing captions
    db.query(CaptionItem).filter(CaptionItem.project_id == project_id).delete()

    new_items = []
    for c in captions:
        item = CaptionItem(
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
    project_id: str, item_id: str, body: CaptionItemUpdate, db: Session = Depends(get_db)
):
    item = (
        db.query(CaptionItem)
        .filter(CaptionItem.id == item_id, CaptionItem.project_id == project_id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Caption item not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return CaptionItemResponse.model_validate(item)


@router.delete("/{project_id}")
def clear_captions(project_id: str, db: Session = Depends(get_db)):
    db.query(CaptionItem).filter(CaptionItem.project_id == project_id).delete()
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/items/{item_id}")
def delete_caption_item(project_id: str, item_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(CaptionItem)
        .filter(CaptionItem.id == item_id, CaptionItem.project_id == project_id)
        .delete()
    )
    if rows == 0:
        raise HTTPException(404, "Caption item not found")
    db.commit()
    return {"ok": True}
