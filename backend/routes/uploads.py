import json
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_workspace
from contracts.media import UploadConfirmRequest, UploadSessionCreate, UploadSessionResponse
from domain.enterprise import OnboardingState
from domain.media import Clip, UploadSession
from domain.projects import Project
from domain.shared import ProcessingStatus
from services.enterprise import check_quota, record_usage
from services.storage import create_upload_path, finalize_uploaded_file, temp_upload_path
from workers.queue import processing_queue

router = APIRouter()


@router.post("/sessions", response_model=UploadSessionResponse)
def create_upload_session(
    body: UploadSessionCreate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    if body.workspace_id != workspace.id:
        raise HTTPException(403, "Workspace mismatch")
    size_mb = float(body.total_size) / (1024 * 1024) if body.total_size is not None else 0.0
    if not check_quota(workspace.id, "storage_mb", size_mb, db):
        raise HTTPException(status_code=429, detail="Storage quota exceeded for this billing period")
    storage_path = create_upload_path(workspace.id, body.filename)
    session = UploadSession(
        workspace_id=workspace.id,
        project_id=body.project_id,
        filename=body.filename,
        storage_path=storage_path,
        total_size=body.total_size,
        media_type=body.media_type,
        status="pending",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    Path(storage_path).parent.mkdir(parents=True, exist_ok=True)
    return session


@router.put("/sessions/{session_id}")
def upload_part(
    session_id: str,
    chunk: bytes = Body(..., media_type="application/octet-stream"),
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    session = db.query(UploadSession).filter(
        UploadSession.id == session_id,
        UploadSession.workspace_id == workspace.id,
    ).first()
    if not session:
        raise HTTPException(404, "Upload session not found")

    path = temp_upload_path(session.id, session.filename)
    with open(path, "ab") as f:
        f.write(chunk)

    session.uploaded_size = path.stat().st_size
    session.status = "uploading"
    db.commit()
    return {"ok": True, "uploaded_size": session.uploaded_size}


@router.post("/sessions/{session_id}/complete")
async def complete_upload(
    session_id: str,
    body: UploadConfirmRequest,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    session = db.query(UploadSession).filter(
        UploadSession.id == session_id,
        UploadSession.workspace_id == workspace.id,
    ).first()
    if not session:
        raise HTTPException(404, "Upload session not found")

    project = db.query(Project).filter(
        Project.id == body.project_id,
        Project.workspace_id == workspace.id,
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")

    temp_path = temp_upload_path(session.id, session.filename)
    stored_path = finalize_uploaded_file(temp_path, session.storage_path)
    session.project_id = project.id
    session.storage_path = stored_path
    session.status = "complete"

    clip = Clip(
        workspace_id=workspace.id,
        project_id=project.id,
        source_path=stored_path,
        status=ProcessingStatus.PENDING,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    record_usage(
        db,
        workspace_id=workspace.id,
        project_id=project.id,
        category="storage_mb",
        quantity=round((body.total_size or session.total_size or 0) / (1024 * 1024), 4),
        unit="mb",
        amount_usd=0.0,
        correlation_id=session.id,
        metadata={"upload_session_id": session.id, "filename": session.filename},
    )
    onboarding = db.query(OnboardingState).filter(OnboardingState.workspace_id == workspace.id).first()
    if onboarding:
        try:
            checklist = json.loads(onboarding.checklist_json or "{}")
        except Exception:
            checklist = {}
        checklist["first_upload"] = True
        onboarding.checklist_json = json.dumps(checklist)
        db.commit()

    await processing_queue.put(clip.id)
    return {"ok": True, "clip_id": clip.id}


@router.get("/sessions/{session_id}", response_model=UploadSessionResponse)
def get_upload_session(
    session_id: str,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    session = db.query(UploadSession).filter(
        UploadSession.id == session_id,
        UploadSession.workspace_id == workspace.id,
    ).first()
    if not session:
        raise HTTPException(404, "Upload session not found")
    return session
