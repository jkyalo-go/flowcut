from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_workspace
from contracts.media import ClipResponse
from domain.media import Clip

router = APIRouter()


@router.get("", response_model=list[ClipResponse])
def list_clips(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return db.query(Clip).filter(Clip.project_id == project_id, Clip.workspace_id == workspace.id).all()


@router.get("/{clip_id}", response_model=ClipResponse)
def get_clip(clip_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    clip = db.query(Clip).filter(Clip.id == clip_id, Clip.workspace_id == workspace.id).first()
    if not clip:
        raise HTTPException(404, "Clip not found")
    return clip
