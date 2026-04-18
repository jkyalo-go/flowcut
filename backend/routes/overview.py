import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_workspace
from domain.ai import AIUsageRecord
from domain.automation import AuditLog
from domain.enterprise import OnboardingState, QuotaPolicy, UsageLedger
from domain.media import Clip
from domain.platforms import CalendarSlot, PlatformConnection
from domain.projects import Project
from domain.shared import ReviewStatus
from routes.platforms import PLATFORM_CAPABILITIES, _serialize_platform_surface

router = APIRouter()

_ONBOARDING_LABELS = {
    "workspace_created": "Workspace created",
    "brand_setup": "Brand defaults configured",
    "provider_policy_configured": "AI provider policy configured",
    "platform_connected": "Platform connected",
    "first_upload": "First upload completed",
    "style_profile_created": "Style profile created",
    "first_publish_ready": "First publish scheduled",
}


def _parse_json(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value)
    except Exception:
        return fallback
    return parsed


def _serialize_slot(row: CalendarSlot) -> dict:
    return {
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
        "metadata": _parse_json(row.metadata_json, {}),
    }


def _serialize_audit(entry: AuditLog) -> dict:
    return {
        "id": entry.id,
        "actor": entry.actor,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "reason": entry.reason,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "metadata": _parse_json(entry.metadata_json, {}),
    }


@router.get("")
def get_overview(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    queue = (
        db.query(Clip)
        .filter(
            Clip.workspace_id == workspace.id,
            Clip.review_status.in_([
                ReviewStatus.PENDING_REVIEW,
                ReviewStatus.AUTO_APPROVED,
                ReviewStatus.FAILED,
            ]),
        )
        .order_by(Clip.created_at.desc())
        .limit(6)
        .all()
    )
    upcoming_slots = (
        db.query(CalendarSlot)
        .filter(CalendarSlot.workspace_id == workspace.id)
        .order_by(CalendarSlot.scheduled_at.asc())
        .limit(8)
        .all()
    )
    platform_rows = db.query(PlatformConnection).filter(PlatformConnection.workspace_id == workspace.id).all()
    by_platform = {row.platform.value: row for row in platform_rows}
    platforms = [
        _serialize_platform_surface(platform, capabilities, by_platform.get(platform))
        for platform, capabilities in PLATFORM_CAPABILITIES.items()
    ]
    connected_count = len([p for p in platforms if p["connected"]])
    ready_count = len([p for p in platforms if p["ready"]])

    quota = db.query(QuotaPolicy).filter(QuotaPolicy.workspace_id == workspace.id).first()
    usage_totals: dict[str, float] = {}
    for category, total in (
        db.query(UsageLedger.category, func.sum(UsageLedger.quantity))
        .filter(UsageLedger.workspace_id == workspace.id)
        .group_by(UsageLedger.category)
        .all()
    ):
        usage_totals[str(category)] = float(total or 0.0)
    usage_totals["ai_spend_usd"] = float(
        db.query(func.sum(AIUsageRecord.cost_estimate)).filter(AIUsageRecord.workspace_id == workspace.id).scalar() or 0.0
    )
    exceeded: list[str] = []
    if quota is not None:
        if usage_totals.get("storage_mb", 0.0) > quota.storage_quota_mb:
            exceeded.append("storage_mb")
        if usage_totals.get("render_minutes", 0.0) > quota.render_minutes_quota:
            exceeded.append("render_minutes")
        if usage_totals.get("ai_spend_usd", 0.0) > quota.ai_spend_cap_usd:
            exceeded.append("ai_spend_usd")

    onboarding_row = db.query(OnboardingState).filter(OnboardingState.workspace_id == workspace.id).first()
    checklist = _parse_json(onboarding_row.checklist_json if onboarding_row else None, {})
    onboarding_items = [
        {
            "key": key,
            "label": _ONBOARDING_LABELS.get(key, key.replace("_", " ").title()),
            "completed": bool(value),
        }
        for key, value in checklist.items()
    ]
    activity = (
        db.query(AuditLog)
        .filter(AuditLog.workspace_id == workspace.id)
        .order_by(AuditLog.created_at.desc())
        .limit(8)
        .all()
    )
    recent_projects = (
        db.query(Project)
        .filter(Project.workspace_id == workspace.id)
        .order_by(Project.created_at.desc())
        .limit(4)
        .all()
    )
    total_projects = db.query(Project).filter(Project.workspace_id == workspace.id).count()

    return {
        "review": {
            "pending": len(queue),
            "items": [
                {
                    "id": clip.id,
                    "clip_id": clip.id,
                    "project_id": clip.project_id,
                    "title": clip.source_path.split("/")[-1] if clip.source_path else "Untitled clip",
                    "status": clip.review_status.value if hasattr(clip.review_status, "value") else str(clip.review_status),
                    "edit_confidence": clip.confidence_score or 0.0,
                    "created_at": clip.created_at.isoformat() if clip.created_at else None,
                    "thumbnail_urls": [],
                }
                for clip in queue
            ],
        },
        "schedule": {
            "upcoming": [_serialize_slot(slot) for slot in upcoming_slots],
            "scheduled_count": db.query(CalendarSlot).filter(CalendarSlot.workspace_id == workspace.id, CalendarSlot.status == "scheduled").count(),
            "failed_count": db.query(CalendarSlot).filter(CalendarSlot.workspace_id == workspace.id, CalendarSlot.status == "failed").count(),
            "published_count": db.query(CalendarSlot).filter(CalendarSlot.workspace_id == workspace.id, CalendarSlot.status == "published").count(),
        },
        "platforms": {
            "items": platforms,
            "connected": connected_count,
            "ready": ready_count,
            "total": len(platforms),
        },
        "quota": {
            "quota": {
                "storage_quota_mb": quota.storage_quota_mb if quota else 0,
                "ai_spend_cap_usd": quota.ai_spend_cap_usd if quota else 0,
                "render_minutes_quota": quota.render_minutes_quota if quota else 0,
                "connected_platforms_quota": quota.connected_platforms_quota if quota else 0,
                "team_seats_quota": quota.team_seats_quota if quota else 0,
                "retained_footage_days": quota.retained_footage_days if quota else 0,
                "automation_max_mode": quota.automation_max_mode if quota else "supervised",
            },
            "usage": usage_totals,
            "exceeded": exceeded,
        },
        "activity": [_serialize_audit(entry) for entry in activity],
        "onboarding": {
            "items": onboarding_items,
            "completed_count": len([item for item in onboarding_items if item["completed"]]),
            "total": len(onboarding_items),
        },
        "projects": {
            "total": total_projects,
            "recent": [
                {
                    "id": project.id,
                    "name": project.name,
                    "created_at": project.created_at.isoformat() if project.created_at else None,
                    "render_path": project.render_path,
                    "clip_count": len(project.clips or []),
                }
                for project in recent_projects
            ],
        },
    }
