import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Project
from services.renderer import render_timeline
from config import PROCESSED_DIR

router = APIRouter()

_render_tasks: dict[int, asyncio.Task] = {}


@router.post("/{project_id}")
async def start_render(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    if project_id in _render_tasks and not _render_tasks[project_id].done():
        raise HTTPException(409, "Render already in progress")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(PROCESSED_DIR / f"project_{project_id}_render.mp4")

    task = asyncio.create_task(render_timeline(project_id, output_path))
    _render_tasks[project_id] = task

    return {"ok": True, "output_path": output_path}


@router.get("/{project_id}/status")
async def render_status(project_id: int):
    task = _render_tasks.get(project_id)
    if not task:
        return {"status": "idle"}
    if task.done():
        if task.exception():
            return {"status": "error", "error": str(task.exception())}
        return {"status": "done"}
    return {"status": "rendering"}


@router.get("/{project_id}/download")
async def download_render(project_id: int):
    path = PROCESSED_DIR / f"project_{project_id}_render.mp4"
    if not path.exists():
        raise HTTPException(404, "Render not found")
    return FileResponse(str(path), media_type="video/mp4", filename=f"render_{project_id}.mp4")
