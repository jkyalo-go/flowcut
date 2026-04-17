import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_workspace
from contracts.platforms import YouTubeUploadRequest
from domain.projects import Project
from services.youtube_service import (
    get_auth_url, exchange_code, get_auth_status,
    upload_video, revoke_credentials,
)
from config import PROCESSED_DIR
from routes.ws import broadcast

logger = logging.getLogger(__name__)
router = APIRouter()

_upload_tasks: dict[str, asyncio.Task] = {}


@router.get("/status")
def youtube_status(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return get_auth_status(db, workspace_id=workspace.id)


@router.get("/auth")
def youtube_auth():
    try:
        url = get_auth_url()
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return {"auth_url": url}


@router.get("/callback")
def youtube_callback(code: str, db: Session = Depends(get_db)):
    try:
        channel_name = exchange_code(code, db)
    except Exception as e:
        logger.error(f"OAuth exchange failed: {e}")
        return HTMLResponse(f"""
            <html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2>Authentication Failed</h2>
            <p>{e}</p>
            <script>setTimeout(()=>window.close(),3000)</script>
            </body></html>
        """)

    return HTMLResponse(f"""
        <html><body style="font-family:sans-serif;text-align:center;padding:60px">
        <h2>Connected to YouTube</h2>
        <p>Signed in as <strong>{channel_name}</strong></p>
        <p>You can close this window.</p>
        <script>setTimeout(()=>window.close(),1500)</script>
        </body></html>
    """)


@router.post("/upload/{project_id}")
async def start_upload(
    project_id: str,
    body: YouTubeUploadRequest,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    render_path = PROCESSED_DIR / f"project_{project_id}_render.mp4"
    if not render_path.exists():
        raise HTTPException(404, "Render not found. Export the video first.")

    if project_id in _upload_tasks and not _upload_tasks[project_id].done():
        raise HTTPException(409, "Upload already in progress")

    loop = asyncio.get_event_loop()

    async def do_upload():
        def progress_cb(pct: int):
            asyncio.run_coroutine_threadsafe(
                broadcast(project_id, "youtube_upload_progress", {"percent": pct}),
                loop,
            )

        try:
            from database import SessionLocal
            upload_db = SessionLocal()
            try:
                video_id = await loop.run_in_executor(
                    None,
                    lambda: upload_video(
                        project_id=project_id,
                        workspace_id=workspace.id,
                        title=body.title,
                        description=body.description,
                        tags=body.tags,
                        category_id=body.category_id,
                        privacy_status=body.privacy_status,
                        thumbnail_index=body.thumbnail_index,
                        db=upload_db,
                        progress_callback=progress_cb,
                    ),
                )
            finally:
                upload_db.close()

            await broadcast(project_id, "youtube_upload_done", {
                "video_id": video_id,
                "video_url": f"https://youtu.be/{video_id}",
            })
        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            await broadcast(project_id, "youtube_upload_error", {"error": str(e)})

    task = asyncio.create_task(do_upload())
    _upload_tasks[project_id] = task

    return {"ok": True}


@router.post("/disconnect")
def youtube_disconnect(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    revoke_credentials(db, workspace_id=workspace.id)
    return {"ok": True}
