import subprocess
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import PROCESSED_DIR
from domain.enterprise import BackgroundJob
from database import get_db
from dependencies import get_current_workspace
from domain.projects import Project
from domain.shared import JobStatus
from services.background_jobs import enqueue_job
from services.storage import download_to_temp

router = APIRouter()


@router.post("/{project_id}")
async def start_render(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    active_job = db.query(BackgroundJob).filter(
        BackgroundJob.job_type == "project_render",
        BackgroundJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
        BackgroundJob.payload_json.contains(f'"project_id": "{project_id}"'),
    ).first()
    if active_job:
        raise HTTPException(409, "Render already in progress")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(PROCESSED_DIR / f"project_{project_id}_render.mp4")
    enqueue_job(
        db,
        workspace_id=workspace.id,
        job_type="project_render",
        correlation_id=project_id,
        payload={"project_id": project_id},
    )

    return {"ok": True, "output_path": output_path}


@router.get("/{project_id}/status")
async def render_status(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    latest_job = db.query(BackgroundJob).filter(
        BackgroundJob.job_type == "project_render",
        BackgroundJob.payload_json.contains(f'"project_id": "{project_id}"'),
    ).order_by(BackgroundJob.created_at.desc()).first()
    if not latest_job:
        return {"status": "done" if project.render_path else "idle"}
    if latest_job.status == JobStatus.SUCCEEDED:
        return {"status": "done"}
    if latest_job.status == JobStatus.RUNNING:
        return {"status": "rendering"}
    if latest_job.status == JobStatus.DEAD_LETTER:
        return {"status": "error", "error": latest_job.last_error}
    return {"status": "rendering"}


@router.post("/{project_id}/reveal")
async def reveal_in_finder(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    render_path = project.render_path or str(PROCESSED_DIR / f"project_{project_id}_render.mp4")
    if str(render_path).startswith("gs://"):
        raise HTTPException(400, "Reveal in Finder is only available for local render storage")
    path = Path(render_path)
    if not path.exists():
        raise HTTPException(404, "Render not found")
    subprocess.run(["open", "-R", str(path)])
    return {"ok": True}


@router.get("/{project_id}/download")
async def download_render(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    path = download_to_temp(project.render_path or str(PROCESSED_DIR / f"project_{project_id}_render.mp4"))
    if not path.exists():
        raise HTTPException(404, "Render not found")
    return FileResponse(str(path), media_type="video/mp4", filename=f"render_{project_id}.mp4")
