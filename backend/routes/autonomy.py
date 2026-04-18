import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from contracts.automation import (
    AuditLogResponse,
    AutonomySettingsResponse,
    AutonomySettingsUpdate,
    NotificationResponse,
    ReviewActionRequest,
)
from contracts.media import ClipResponse
from contracts.platforms import CalendarSlotResponse
from database import get_db
from dependencies import get_current_user, get_current_workspace
from domain.automation import AuditLog, Notification
from domain.media import Clip
from domain.platforms import CalendarSlot
from domain.projects import Project
from domain.shared import ReviewStatus
from services.audit import create_notification, record_audit

router = APIRouter()


def _parse_platforms(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


@router.get("/settings", response_model=AutonomySettingsResponse)
def get_workspace_autonomy(
    project_id: str | None = Query(default=None),
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    # Workspace-level defaults
    mode = workspace.autonomy_mode.value
    threshold = workspace.autonomy_confidence_threshold

    if project_id:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.workspace_id == workspace.id,
        ).first()
        if project:
            if project.autonomy_mode is not None:
                mode = project.autonomy_mode.value
            if project.autonomy_confidence_threshold is not None:
                threshold = project.autonomy_confidence_threshold

    return AutonomySettingsResponse(
        workspace_id=workspace.id,
        project_id=project_id,
        autonomy_mode=mode,
        confidence_threshold=threshold,
        allowed_platforms=_parse_platforms(workspace.autopublish_platforms),
        quiet_hours=workspace.quiet_hours,
        notification_preferences=workspace.notification_preferences,
    )


@router.post("/settings", response_model=AutonomySettingsResponse)
def update_autonomy(
    body: AutonomySettingsUpdate,
    workspace=Depends(get_current_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.project_id:
        project = db.query(Project).filter(
            Project.id == body.project_id,
            Project.workspace_id == workspace.id,
        ).first()
        if not project:
            raise HTTPException(404, "Project not found")
        project.autonomy_mode = body.autonomy_mode
        project.autonomy_confidence_threshold = body.confidence_threshold
        db.commit()
        record_audit(
            db,
            workspace_id=workspace.id,
            actor="user",
            user_id=user.id,
            action="autonomy.project_settings_updated",
            target_type="project",
            target_id=str(project.id),
            metadata=body.model_dump(),
        )
    else:
        workspace.autonomy_mode = body.autonomy_mode
        workspace.autonomy_confidence_threshold = body.confidence_threshold or workspace.autonomy_confidence_threshold
        workspace.autopublish_platforms = json.dumps(body.allowed_platforms)
        workspace.quiet_hours = body.quiet_hours
        workspace.notification_preferences = body.notification_preferences
        db.commit()
        record_audit(
            db,
            workspace_id=workspace.id,
            actor="user",
            user_id=user.id,
            action="autonomy.settings_updated",
            target_type="workspace",
            target_id=str(workspace.id),
            metadata=body.model_dump(),
        )
    return get_workspace_autonomy(project_id=body.project_id, workspace=workspace, db=db)


@router.put("/settings", response_model=AutonomySettingsResponse)
def update_workspace_autonomy(
    body: AutonomySettingsUpdate,
    workspace=Depends(get_current_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_autonomy(body, workspace, user, db)


@router.get("/review-queue", response_model=list[ClipResponse])
def review_queue(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return db.query(Clip).filter(
        Clip.workspace_id == workspace.id,
        Clip.review_status.in_([
            ReviewStatus.PENDING_REVIEW,
            ReviewStatus.AUTO_APPROVED,
            ReviewStatus.FAILED,
        ]),
    ).order_by(Clip.id.desc()).all()


@router.post("/review-queue/{clip_id}")
async def apply_review_action(
    clip_id: str,
    body: ReviewActionRequest,
    workspace=Depends(get_current_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clip = db.query(Clip).filter(
        Clip.id == clip_id,
        Clip.workspace_id == workspace.id,
    ).first()
    if not clip:
        raise HTTPException(404, "Clip not found")

    action_map = {
        "approve": ReviewStatus.APPROVED,
        "reject": ReviewStatus.REJECTED,
        "schedule": ReviewStatus.SCHEDULED,
    }
    if body.action not in action_map:
        raise HTTPException(400, "Unsupported review action")
    clip.review_status = action_map[body.action]
    db.commit()
    record_audit(
        db,
        workspace_id=workspace.id,
        actor="user",
        user_id=user.id,
        action=f"clip.{body.action}",
        target_type="clip",
        target_id=str(clip.id),
        reason=body.reason,
    )

    if body.action == "reject" and body.corrections:
        from services.sie.re_planner import re_plan_clip
        asyncio.create_task(re_plan_clip(str(clip.id), body.corrections))

    if body.action == "approve" and body.edit_manifest_override:
        override = body.edit_manifest_override
        if override and getattr(clip, 'edit_manifest', None):
            try:
                from services.sie.feedback import apply_feedback_to_profile, diff_manifests
                profile = None
                if getattr(clip, 'profile_id', None):
                    from domain.projects import StyleProfile
                    profile = db.query(StyleProfile).filter(StyleProfile.id == clip.profile_id).first()
                original = json.loads(clip.edit_manifest)
                diff = diff_manifests(original, override)
                if diff and profile:
                    style_dict = json.loads(profile.style_doc or "{}")
                    locks = json.loads(profile.dimension_locks or "{}")
                    updated = apply_feedback_to_profile(style_dict, diff, locks, action="modified")
                    profile.style_doc = json.dumps(updated)
                    profile.version = (profile.version or 1) + 1
                    db.commit()
            except Exception:
                pass

    return {"ok": True, "review_status": clip.review_status.value}


@router.get("/calendar", response_model=list[CalendarSlotResponse])
def list_calendar(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return db.query(CalendarSlot).filter(CalendarSlot.workspace_id == workspace.id).order_by(CalendarSlot.id.desc()).all()


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(workspace=Depends(get_current_workspace), user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Notification).filter(
        Notification.workspace_id == workspace.id
    ).order_by(Notification.id.desc()).limit(100).all()


@router.post("/notifications/test")
def push_test_notification(workspace=Depends(get_current_workspace), user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = create_notification(
        db,
        workspace_id=workspace.id,
        user_id=user.id,
        category="processing",
        title="Flowcut test notification",
        body="Your automation center is configured and ready.",
        metadata={"kind": "test"},
    )
    return {"ok": True, "notification_id": row.id}


@router.get("/audit", response_model=list[AuditLogResponse])
def list_audit_log(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    return db.query(AuditLog).filter(AuditLog.workspace_id == workspace.id).order_by(AuditLog.id.desc()).limit(200).all()
