from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Clip
from schemas import ClipResponse

router = APIRouter()


@router.get("", response_model=list[ClipResponse])
def list_clips(project_id: int, db: Session = Depends(get_db)):
    return db.query(Clip).filter(Clip.project_id == project_id).all()


@router.get("/{clip_id}", response_model=ClipResponse)
def get_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(404, "Clip not found")
    return clip
