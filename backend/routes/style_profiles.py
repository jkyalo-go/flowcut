import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from domain.projects import StyleProfile
from routes.auth import get_current_session
from services.sie.cold_start import get_genre_centroid, SUPPORTED_GENRES

router = APIRouter(prefix="/style-profiles", tags=["style-profiles"])


@router.get("/genres")
def list_genres():
    return {"genres": SUPPORTED_GENRES}


@router.post("")
def create_profile(payload: dict, db: Session = Depends(get_db), session=Depends(get_current_session)):
    genre = payload.get("genre", "vlog")
    centroid = get_genre_centroid(genre)
    profile = StyleProfile(
        workspace_id=session.workspace_id,
        project_id=payload.get("project_id"),
        name=payload.get("name", f"{genre.title()} Profile"),
        genre=genre,
        style_doc=json.dumps(centroid),
        confidence_scores="{}",
        dimension_locks="{}",
        version=1,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _serialize(profile)


@router.get("")
def list_profiles(db: Session = Depends(get_db), session=Depends(get_current_session)):
    profiles = db.query(StyleProfile).filter(StyleProfile.workspace_id == session.workspace_id).all()
    return {"profiles": [_serialize(p) for p in profiles]}


@router.get("/{profile_id}")
def get_profile(profile_id: str, db: Session = Depends(get_db), session=Depends(get_current_session)):
    p = _get_or_404(profile_id, session.workspace_id, db)
    return _serialize(p)


@router.put("/{profile_id}/locks")
def update_locks(profile_id: str, payload: dict, db: Session = Depends(get_db),
                 session=Depends(get_current_session)):
    p = _get_or_404(profile_id, session.workspace_id, db)
    locks = json.loads(p.dimension_locks or "{}")
    locks.update(payload.get("dimension_locks", {}))
    p.dimension_locks = json.dumps(locks)
    db.commit()
    return {"dimension_locks": locks}


@router.post("/{profile_id}/rollback")
def rollback_profile(profile_id: str, payload: dict, db: Session = Depends(get_db),
                     session=Depends(get_current_session)):
    p = _get_or_404(profile_id, session.workspace_id, db)
    target = payload.get("target_version", 1)
    if target == 1 and p.genre:
        p.style_doc = json.dumps(get_genre_centroid(p.genre))
        p.version = 1
        db.commit()
    return _serialize(p)


def _get_or_404(profile_id: str, workspace_id: str, db: Session) -> StyleProfile:
    p = db.query(StyleProfile).filter(
        StyleProfile.id == profile_id,
        StyleProfile.workspace_id == workspace_id,
    ).first()
    if not p:
        raise HTTPException(404, "Style profile not found")
    return p


def _serialize(p: StyleProfile) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "genre": p.genre,
        "style_doc": json.loads(p.style_doc or "{}"),
        "confidence_scores": json.loads(p.confidence_scores or "{}"),
        "dimension_locks": json.loads(p.dimension_locks or "{}"),
        "version": p.version,
    }
