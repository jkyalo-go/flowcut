from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Project
from schemas import ProjectCreate, ProjectResponse
from services.watcher import start_watching, stop_watching, get_watcher_state

router = APIRouter()


@router.post("", response_model=ProjectResponse)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    path = Path(body.watch_directory)
    if not path.is_dir():
        raise HTTPException(400, f"Directory does not exist: {body.watch_directory}")
    project = Project(name=body.name, watch_directory=body.watch_directory)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    stop_watching(project_id)
    db.delete(project)
    db.commit()
    return {"ok": True}


@router.post("/{project_id}/watch/start")
def start_watch(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    new_clip_ids = start_watching(project_id, project.watch_directory)
    # Return the newly found clips so the frontend has them immediately
    from models import Clip
    clips = db.query(Clip).filter(Clip.project_id == project_id).all()
    from schemas import ClipResponse
    return {
        "ok": True,
        "watching": project.watch_directory,
        "clips": [ClipResponse.from_orm(c) for c in clips],
    }


@router.post("/{project_id}/watch/stop")
def stop_watch(project_id: int):
    stop_watching(project_id)
    return {"ok": True}


@router.get("/debug/watcher")
def debug_watcher(db: Session = Depends(get_db)):
    from models import Clip
    watcher = get_watcher_state()
    # Count clips per project
    from sqlalchemy import func
    clip_counts = db.query(Clip.project_id, Clip.source_path, Clip.status).all()
    clips_by_project: dict[int, list] = {}
    for pid, path, status in clip_counts:
        clips_by_project.setdefault(pid, []).append({"path": path.split("/")[-1], "status": status.value if status else None})
    return {
        "watcher": watcher,
        "clips_by_project": {k: {"count": len(v), "clips": v} for k, v in clips_by_project.items()},
    }
