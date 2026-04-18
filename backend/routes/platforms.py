import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, get_current_workspace
from contracts.platforms import PlatformConnectionCreate, PlatformConnectionResponse, PublishRequest
from domain.enterprise import OnboardingState
from domain.media import Clip
from domain.platforms import CalendarSlot, PlatformConnection
from domain.projects import Project
from domain.shared import PlatformType, ReviewStatus
from services.audit import create_notification, record_audit
from services.background_jobs import enqueue_job, ensure_due_publish_jobs, process_available_jobs
from services.enterprise import record_admin_action
from services.platform_auth import complete_platform_auth, disconnect_platform_auth, ensure_valid_platform_connection, platform_auth_start, platform_auth_status
from services.platform_integrations import execute_slot

router = APIRouter()


PLATFORM_CAPABILITIES = {
    PlatformType.YOUTUBE.value: {
        "label": "YouTube",
        "auth_mode": "oauth",
        "required_connection_fields": [],
        "aspect_ratios": ["16:9", "9:16"],
        "duration_limit_seconds": 43200,
        "supports_thumbnail": True,
        "supports_scheduling": False,
        "title_limit": 100,
        "body_limit": 5000,
        "requires_public_video_url": False,
    },
    PlatformType.TIKTOK.value: {
        "label": "TikTok",
        "auth_mode": "oauth",
        "required_connection_fields": ["access_token"],
        "aspect_ratios": ["9:16"],
        "duration_limit_seconds": 600,
        "supports_thumbnail": False,
        "supports_scheduling": False,
        "title_limit": 150,
        "body_limit": 2200,
        "requires_public_video_url": False,
    },
    PlatformType.INSTAGRAM_REELS.value: {
        "label": "Instagram Reels",
        "auth_mode": "oauth",
        "required_connection_fields": ["access_token", "ig_user_id"],
        "aspect_ratios": ["9:16"],
        "duration_limit_seconds": 900,
        "supports_thumbnail": True,
        "supports_scheduling": True,
        "title_limit": 2200,
        "body_limit": 2200,
        "requires_public_video_url": True,
    },
    PlatformType.LINKEDIN.value: {
        "label": "LinkedIn",
        "auth_mode": "oauth",
        "required_connection_fields": ["access_token", "author_urn"],
        "aspect_ratios": ["16:9", "1:1", "9:16"],
        "duration_limit_seconds": 600,
        "supports_thumbnail": True,
        "supports_scheduling": True,
        "title_limit": 200,
        "body_limit": 3000,
        "requires_public_video_url": False,
    },
    PlatformType.X.value: {
        "label": "X",
        "auth_mode": "oauth",
        "required_connection_fields": ["access_token"],
        "aspect_ratios": ["16:9", "1:1", "9:16"],
        "duration_limit_seconds": 140,
        "supports_thumbnail": False,
        "supports_scheduling": False,
        "title_limit": 280,
        "body_limit": 280,
        "requires_public_video_url": False,
    },
}


def _connection_metadata(row: PlatformConnection | None) -> dict:
    if not row or not row.metadata_json:
        return {}
    try:
        value = json.loads(row.metadata_json)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _platform_requirements_status(platform: str, row: PlatformConnection | None) -> dict:
    capabilities = PLATFORM_CAPABILITIES[platform]
    metadata = _connection_metadata(row)
    checks = {
        "access_token": bool(row and row.access_token),
        "refresh_token": bool(row and row.refresh_token),
        "account_id": bool(row and row.account_id),
        "ig_user_id": bool(metadata.get("ig_user_id")),
        "author_urn": bool(metadata.get("author_urn")),
    }
    required_fields = capabilities.get("required_connection_fields", [])
    missing = [field for field in required_fields if not checks.get(field)]
    return {
        "required_fields": required_fields,
        "missing_fields": missing,
        "ready": row is not None and not missing,
    }


def _serialize_platform_surface(platform: str, capabilities: dict, row: PlatformConnection | None) -> dict:
    requirements = _platform_requirements_status(platform, row)
    metadata = _connection_metadata(row)
    status = "not_connected"
    if row:
        status = "active"
        if row.token_expiry:
            now = datetime.now(timezone.utc)
            compare_now = now if getattr(row.token_expiry, "tzinfo", None) else now.replace(tzinfo=None)
            if row.token_expiry <= compare_now:
                status = "expired"

    return {
        "platform": platform,
        "label": capabilities["label"],
        "connected": row is not None,
        "ready": requirements["ready"],
        "status": status,
        "display_name": (row.account_name or row.account_id or capabilities["label"]) if row else capabilities["label"],
        "scopes": metadata.get("scopes", []),
        "auth_mode": capabilities["auth_mode"],
        "supports_thumbnail": capabilities["supports_thumbnail"],
        "supports_scheduling": capabilities["supports_scheduling"],
        "aspect_ratios": capabilities["aspect_ratios"],
        "duration_limit_seconds": capabilities["duration_limit_seconds"],
        "title_limit": capabilities["title_limit"],
        "body_limit": capabilities["body_limit"],
        "required_fields": requirements["required_fields"],
        "missing_fields": requirements["missing_fields"],
        "connection": PlatformConnectionResponse.model_validate(row).model_dump() if row else None,
    }


@router.get("")
def list_platforms(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    rows = db.query(PlatformConnection).filter(PlatformConnection.workspace_id == workspace.id).all()
    rows = [ensure_valid_platform_connection(db, row) for row in rows]
    by_platform = {row.platform.value: row for row in rows}
    return {
        "platforms": [
            _serialize_platform_surface(platform, capabilities, by_platform.get(platform))
            for platform, capabilities in PLATFORM_CAPABILITIES.items()
        ]
    }


@router.post("/{platform}", response_model=PlatformConnectionResponse)
def connect_platform(
    platform: str,
    body: PlatformConnectionCreate,
    workspace=Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    if platform not in PLATFORM_CAPABILITIES:
        raise HTTPException(404, "Unsupported platform")

    row = db.query(PlatformConnection).filter(
        PlatformConnection.workspace_id == workspace.id,
        PlatformConnection.platform == platform,
    ).first()
    if row:
        row.account_name = body.account_name
        row.account_id = body.account_id
        row.access_token = body.access_token
        row.refresh_token = body.refresh_token
        row.metadata_json = body.metadata_json
        row.token_expiry = datetime.now(timezone.utc) + timedelta(days=30)
    else:
        row = PlatformConnection(
            workspace_id=workspace.id,
            platform=platform,
            account_name=body.account_name or body.platform.title(),
            account_id=body.account_id,
            access_token=body.access_token,
            refresh_token=body.refresh_token,
            metadata_json=body.metadata_json or json.dumps({"connected_via": "manual"}),
            token_expiry=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    onboarding = db.query(OnboardingState).filter(OnboardingState.workspace_id == workspace.id).first()
    if onboarding:
        try:
            checklist = json.loads(onboarding.checklist_json or "{}")
        except Exception:
            checklist = {}
        checklist["platform_connected"] = True
        onboarding.checklist_json = json.dumps(checklist)
        db.commit()
    return row


@router.get("/{platform}/auth/status")
def get_platform_auth_status(platform: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    if platform not in PLATFORM_CAPABILITIES:
        raise HTTPException(404, "Unsupported platform")
    return platform_auth_status(db, workspace.id, platform)


@router.get("/{platform}/auth/start")
def start_platform_auth(platform: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    if platform not in PLATFORM_CAPABILITIES:
        raise HTTPException(404, "Unsupported platform")
    try:
        response = platform_auth_start(db, platform, workspace.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {
        "platform": platform,
        "mode": response.mode,
        "auth_url": response.auth_url,
        "url": response.auth_url,
        "instructions": response.instructions,
        "required_fields": response.required_fields or [],
    }


@router.get("/{platform}/callback")
def complete_auth_callback(
    platform: str,
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    if platform not in PLATFORM_CAPABILITIES:
        raise HTTPException(404, "Unsupported platform")
    try:
        row = complete_platform_auth(db, None, platform, code, state)
    except Exception as exc:
        return HTMLResponse(
            f"""
            <html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2>Authentication Failed</h2>
            <p>{exc}</p>
            <script>setTimeout(()=>window.close(),3000)</script>
            </body></html>
            """,
            status_code=400,
        )
    return HTMLResponse(
        f"""
        <html><body style="font-family:sans-serif;text-align:center;padding:60px">
        <h2>Connected to {PLATFORM_CAPABILITIES[platform]["label"]}</h2>
        <p>Signed in as <strong>{row.account_name or row.account_id or "connected account"}</strong></p>
        <p>You can close this window.</p>
        <script>setTimeout(()=>window.close(),1500)</script>
        </body></html>
        """
    )


@router.get("/calendar")
def list_platform_calendar(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    rows = db.query(CalendarSlot).filter(
        CalendarSlot.workspace_id == workspace.id
    ).order_by(CalendarSlot.created_at.desc()).limit(100).all()
    return {
        "slots": [
            {
                "id": row.id,
                "platform": row.platform.value if hasattr(row.platform, "value") else str(row.platform),
                "project_id": row.project_id,
                "clip_id": row.clip_id,
                "render_variant": row.render_variant,
                "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
                "status": row.status,
                "publish_url": row.publish_url,
                "failure_reason": row.failure_reason,
                "retry_count": row.retry_count,
                "correlation_id": row.correlation_id,
                "metadata_json": row.metadata_json,
            }
            for row in rows
        ]
    }


@router.delete("/{platform}")
def disconnect_platform(platform: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    if platform not in PLATFORM_CAPABILITIES:
        raise HTTPException(404, "Unsupported platform")
    row = db.query(PlatformConnection).filter(
        PlatformConnection.workspace_id == workspace.id,
        PlatformConnection.platform == platform,
    ).first()
    if not row and platform != PlatformType.YOUTUBE.value:
        raise HTTPException(404, "Platform connection not found")
    disconnect_platform_auth(db, workspace.id, platform)
    return {"ok": True}


@router.post("/projects/{project_id}/publish")
def publish_project(
    project_id: str,
    body: PublishRequest,
    workspace=Depends(get_current_workspace),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id, Project.workspace_id == workspace.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if not body.platforms:
        raise HTTPException(400, "At least one platform is required")

    clips = db.query(Clip).filter(Clip.project_id == project.id, Clip.workspace_id == workspace.id).all()

    created_slots = []
    execute_now = not body.scheduled_at
    scheduled_for = datetime.fromisoformat(body.scheduled_at) if body.scheduled_at else datetime.now(timezone.utc)
    correlation_id = uuid4().hex
    render_variants = body.render_variants or ["default"]
    for platform in body.platforms:
        if platform not in PLATFORM_CAPABILITIES:
            raise HTTPException(400, f"Unsupported platform: {platform}")
        connection = db.query(PlatformConnection).filter(
            PlatformConnection.workspace_id == workspace.id,
            PlatformConnection.platform == platform,
        ).first()
        if not connection:
            raise HTTPException(400, f"{platform} is not connected")
        if not _platform_requirements_status(platform, connection)["ready"]:
            raise HTTPException(400, f"{platform} is not ready to publish")
        overrides = body.platform_overrides.get(platform, {})

        for render_variant in render_variants:
            slot = CalendarSlot(
                workspace_id=workspace.id,
                project_id=project.id,
                clip_id=None,
                render_variant=render_variant,
                platform=platform,
                scheduled_at=scheduled_for,
                status="scheduled",
                correlation_id=correlation_id,
                metadata_json=json.dumps({
                    "title": overrides.get("title", body.title),
                    "description": overrides.get("description", body.description),
                    "tags": overrides.get("tags", body.tags),
                    "privacy_status": overrides.get("privacy_status", body.privacy_status),
                    "thumbnail_index": overrides.get("thumbnail_index", body.thumbnail_index),
                    "render_variant": render_variant,
                    "platform_override": overrides,
                }),
            )
            db.add(slot)
            created_slots.append(slot)
    db.commit()

    for clip in clips:
        clip.review_status = ReviewStatus.SCHEDULED
    db.commit()

    for slot in created_slots:
        record_audit(
            db,
            workspace_id=workspace.id,
            actor="system" if (project.autonomy_mode and project.autonomy_mode.value == "auto_publish") else "user",
            action="calendar.slot_scheduled",
            target_type="calendar_slot",
            target_id=str(slot.id),
            metadata={
                "platform": slot.platform.value if hasattr(slot.platform, "value") else str(slot.platform),
                "render_variant": slot.render_variant,
                "correlation_id": slot.correlation_id,
            },
        )

    create_notification(
        db,
        workspace_id=workspace.id,
        category="calendar",
        title="Flowcut publish schedule updated",
        body=f"Scheduled {len(created_slots)} publish jobs across {len(body.platforms)} platforms.",
        metadata={"project_id": project.id, "platforms": body.platforms, "correlation_id": correlation_id},
    )
    executed_count = 0
    failed_count = 0
    if execute_now:
        for slot in created_slots:
            enqueue_job(
                db,
                workspace_id=workspace.id,
                job_type="publish_execute",
                correlation_id=slot.correlation_id or slot.id,
                idempotency_key=f"publish_execute:{slot.id}:{slot.retry_count}",
                payload={"slot_id": slot.id},
            )
        executed_count = len(created_slots)

    if hasattr(user, "user_type") and getattr(user, "user_type", "user") == "admin":
        record_admin_action(
            db,
            admin_user_id=user.id,
            action="platform.publish_project",
            target_type="project",
            target_id=project.id,
            metadata={"platforms": body.platforms, "render_variants": render_variants, "correlation_id": correlation_id},
        )

    onboarding = db.query(OnboardingState).filter(OnboardingState.workspace_id == workspace.id).first()
    if onboarding:
        try:
            checklist = json.loads(onboarding.checklist_json or "{}")
        except Exception:
            checklist = {}
        checklist["first_publish_ready"] = True
        onboarding.checklist_json = json.dumps(checklist)
        db.commit()

    return {
        "ok": True,
        "scheduled_slots": len(created_slots),
        "executed_slots": executed_count,
        "failed_slots": failed_count,
        "correlation_id": correlation_id,
        "slot_ids": [slot.id for slot in created_slots],
    }


@router.post("/calendar/run-due")
def run_due_publishes(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    queued = ensure_due_publish_jobs(db, workspace_id=workspace.id)
    processed = process_available_jobs(db, limit=50)
    return {"ok": True, "queued_jobs": queued, "executed_slots": processed}


@router.post("/calendar/{slot_id}/execute")
def execute_calendar_slot(slot_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    slot = db.query(CalendarSlot).filter(CalendarSlot.id == slot_id, CalendarSlot.workspace_id == workspace.id).first()
    if not slot:
        raise HTTPException(404, "Calendar slot not found")
    enqueue_job(
        db,
        workspace_id=workspace.id,
        job_type="publish_execute" if slot.status == "scheduled" else "publish_sync",
        correlation_id=slot.correlation_id or slot.id,
        idempotency_key=f"manual_publish:{slot.id}:{slot.retry_count}:{slot.status}",
        payload={"slot_id": slot.id},
    )
    process_available_jobs(db, limit=10)
    db.refresh(slot)
    return {
        "ok": True,
        "slot_id": slot.id,
        "status": slot.status,
        "publish_url": slot.publish_url,
        "failure_reason": slot.failure_reason,
        "correlation_id": slot.correlation_id,
    }


@router.post("/calendar/{slot_id}/retry")
def retry_calendar_slot(slot_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    slot = db.query(CalendarSlot).filter(CalendarSlot.id == slot_id, CalendarSlot.workspace_id == workspace.id).first()
    if not slot:
        raise HTTPException(404, "Calendar slot not found")
    slot.status = "scheduled"
    slot.failure_reason = None
    db.commit()
    enqueue_job(
        db,
        workspace_id=workspace.id,
        job_type="publish_execute",
        correlation_id=slot.correlation_id or slot.id,
        idempotency_key=f"retry_publish:{slot.id}:{slot.retry_count}",
        payload={"slot_id": slot.id},
    )
    process_available_jobs(db, limit=10)
    return {"ok": True, "slot_id": slot.id, "status": slot.status}


@router.post("/calendar/{slot_id}/cancel")
def cancel_calendar_slot(slot_id: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    slot = db.query(CalendarSlot).filter(CalendarSlot.id == slot_id, CalendarSlot.workspace_id == workspace.id).first()
    if not slot:
        raise HTTPException(404, "Calendar slot not found")
    slot.status = "cancelled"
    db.commit()
    return {"ok": True, "slot_id": slot.id, "status": slot.status}


@router.post("/calendar/{slot_id}/reschedule")
def reschedule_calendar_slot(slot_id: str, scheduled_at: str, workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    slot = db.query(CalendarSlot).filter(CalendarSlot.id == slot_id, CalendarSlot.workspace_id == workspace.id).first()
    if not slot:
        raise HTTPException(404, "Calendar slot not found")
    slot.scheduled_at = datetime.fromisoformat(scheduled_at)
    slot.status = "scheduled"
    slot.failure_reason = None
    db.commit()
    return {"ok": True, "slot_id": slot.id, "status": slot.status, "scheduled_at": slot.scheduled_at.isoformat()}
