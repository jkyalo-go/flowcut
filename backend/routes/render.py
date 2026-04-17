import asyncio
import subprocess
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from config import GCS_MEDIA_BUCKET, PROCESSED_DIR, STORAGE_BACKEND
from database import get_db
from dependencies import get_current_workspace
from domain.projects import Project
from services.renderer import render_timeline
from services.storage import download_to_temp, finalize_uploaded_file

router = APIRouter()

_render_tasks: dict[str, asyncio.Task] = {}


@router.post("/{project_id}")
async def start_render(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    if project_id in _render_tasks and not _render_tasks[project_id].done():
        raise HTTPException(409, "Render already in progress")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(PROCESSED_DIR / f"project_{project_id}_render.mp4")

    async def do_render():
        await render_timeline(project_id, output_path)
        persisted_render_path = output_path
        if STORAGE_BACKEND == "gcs" and GCS_MEDIA_BUCKET:
            persisted_render_path = finalize_uploaded_file(
                Path(output_path),
                f"gs://{GCS_MEDIA_BUCKET}/ws_{workspace.id}/renders/project_{project_id}_render.mp4",
            )
        # Save render path to DB
        from database import SessionLocal
        render_db = SessionLocal()
        try:
            p = render_db.query(Project).filter(Project.id == project_id).first()
            if p:
                p.render_path = persisted_render_path
                render_db.commit()
        finally:
            render_db.close()

    task = asyncio.create_task(do_render())
    _render_tasks[project_id] = task

    return {"ok": True, "output_path": output_path}


@router.get("/{project_id}/status")
async def render_status(project_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    task = _render_tasks.get(project_id)
    if not task:
        return {"status": "idle"}
    if task.done():
        if task.exception():
            return {"status": "error", "error": str(task.exception())}
        return {"status": "done"}
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
