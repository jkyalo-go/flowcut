from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_workspace
from contracts.media import ClipResponse
from contracts.projects import ProjectCreate, ProjectMetadataUpdate, ProjectResponse
from domain.media import Clip
from domain.projects import Project
from services.watcher import start_watching, stop_watching, get_watcher_state

router = APIRouter()


@router.post("", response_model=ProjectResponse)
def create_project(
    body: ProjectCreate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    if body.workspace_id != workspace.id:
        raise HTTPException(403, "Workspace mismatch")
    watch_directory = (body.watch_directory or "").strip() or None
    if body.intake_mode == "watch":
        if not watch_directory:
            raise HTTPException(400, "watch_directory is required for watch intake mode")
        path = Path(watch_directory)
        if not path.is_dir():
            raise HTTPException(400, f"Directory does not exist: {body.watch_directory}")
    project = Project(
        workspace_id=workspace.id,
        name=body.name,
        watch_directory=watch_directory,
        intake_mode=body.intake_mode,
        source_type="folder" if body.intake_mode == "watch" else "upload",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return db.query(Project).filter(Project.workspace_id == workspace.id).all()


@router.put("/{project_id}/metadata")
def update_metadata(project_id: str, body: ProjectMetadataUpdate, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}")
def delete_project(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    stop_watching(project_id)
    db.delete(project)
    db.commit()
    return {"ok": True}


@router.post("/{project_id}/watch/start")
def start_watch(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.watch_directory:
        raise HTTPException(400, "This project does not have a watched folder configured")
    new_clip_ids = start_watching(project_id, project.watch_directory)
    # Return the newly found clips so the frontend has them immediately
    clips = db.query(Clip).filter(Clip.project_id == project_id, Clip.workspace_id == workspace.id).all()
    return {
        "ok": True,
        "watching": project.watch_directory,
        "clips": [ClipResponse.model_validate(c).model_dump() for c in clips],
    }


@router.post("/{project_id}/watch/stop")
def stop_watch(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    stop_watching(project_id)
    return {"ok": True}


@router.get("/debug/watcher")
def debug_watcher(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    watcher = get_watcher_state()
    # Count clips per project
    clip_counts = db.query(Clip.project_id, Clip.source_path, Clip.status).filter(Clip.workspace_id == workspace.id).all()
    clips_by_project: dict[str, list] = {}
    for pid, path, status in clip_counts:
        clips_by_project.setdefault(pid, []).append({"path": path.split("/")[-1], "status": status.value if status else None})
    return {
        "watcher": watcher,
        "clips_by_project": {k: {"count": len(v), "clips": v} for k, v in clips_by_project.items()},
    }
