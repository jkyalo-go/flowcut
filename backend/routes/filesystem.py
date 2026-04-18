import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from config import PROCESSED_DIR, STORAGE_DIR, UPLOAD_TMP_DIR
from database import get_db
from dependencies import get_current_workspace
from domain.media import Asset, Clip, TrackerItem
from domain.projects import Project
from services.storage import download_to_temp, is_gcs_uri, resolve_storage_path, signed_url_for

logger = logging.getLogger(__name__)

router = APIRouter()


ALLOWED_LOCAL_ROOTS = tuple(
    path.resolve()
    for path in {
        STORAGE_DIR,
        PROCESSED_DIR,
        UPLOAD_TMP_DIR,
        PROCESSED_DIR.parent,
    }
)


def _path_in_allowed_roots(path: Path) -> bool:
    # Reject symlinks outright — resolve() follows them, which could have let
    # a symlink under STORAGE_DIR escape to an arbitrary location. Check
    # every component of the real path against both a strict commonpath
    # comparison AND the symlink-status of every intermediate directory.
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        return False
    # Any path component pointing at a symlink is suspect — refuse.
    current = resolved
    while True:
        if current.is_symlink():
            return False
        parent = current.parent
        if parent == current:
            break
        current = parent
    # commonpath-based containment check (more robust than is_relative_to
    # because it operates on the fully-resolved real path).
    resolved_str = str(resolved)
    for root in ALLOWED_LOCAL_ROOTS:
        try:
            if os.path.commonpath([resolved_str, str(root)]) == str(root):
                return True
        except ValueError:
            # Different drives on Windows, or incompatible paths — not a match.
            continue
    return False


def _workspace_owns_path(db: Session, workspace_id: str, path: str) -> bool:
    if not path:
        return False
    if db.query(Clip.id).filter(
        Clip.workspace_id == workspace_id,
        or_(Clip.source_path == path, Clip.processed_path == path),
    ).first():
        return True
    if db.query(Asset.id).filter(Asset.workspace_id == workspace_id, Asset.file_path == path).first():
        return True
    if db.query(TrackerItem.id).filter(TrackerItem.workspace_id == workspace_id, TrackerItem.overlay_path == path).first():
        return True
    if db.query(Project.id).filter(Project.workspace_id == workspace_id, Project.render_path == path).first():
        return True
    return False


def _resolve_authorized_path(path: str, workspace_id: str, db: Session) -> Path:
    if not _workspace_owns_path(db, workspace_id, path):
        raise HTTPException(403, "File is not accessible from this workspace")
    resolved = download_to_temp(path)
    if is_gcs_uri(path):
        return resolved
    candidate = resolved if resolved.exists() else resolve_storage_path(path)
    if not _path_in_allowed_roots(candidate):
        raise HTTPException(403, "Path is outside allowed workspace storage")
    return candidate


@router.get("/serve-video")
async def serve_video(
    path: str = Query(...),
    request: Request = None,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Serve a video file from the local filesystem for timeline playback."""
    p = _resolve_authorized_path(path, workspace.id, db)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "File not found")

    range_header = request.headers.get("range") if request else None
    file_size = p.stat().st_size
    logger.debug("serve-video name=%s size=%d range=%s", p.name, file_size, range_header)

    suffix = p.suffix.lower()
    media_types = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }
    media_type = media_types.get(suffix, "video/mp4")
    return FileResponse(str(p), media_type=media_type)


@router.get("/storage-file")
async def serve_storage_file(path: str = Query(...), workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    p = _resolve_authorized_path(path, workspace.id, db)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "Stored file not found")
    return FileResponse(str(p))


@router.get("/signed-url")
async def get_signed_url(path: str = Query(...), workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    _resolve_authorized_path(path, workspace.id, db)
    url = signed_url_for(path)
    if not url:
        raise HTTPException(400, "Signed URL is only available for GCS-backed assets")
    return {"url": url}
