import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from contracts.enterprise import (
    AdminSummaryResponse,
    ComplianceExportCreate,
    ComplianceExportResponse,
    OnboardingStateResponse,
    QuotaPolicyResponse,
    QuotaStatusResponse,
    SubscriptionPlanResponse,
    UsageLedgerResponse,
    WorkspaceSubscriptionResponse,
    WorkspaceSubscriptionUpdate,
)
from database import get_db
from dependencies import get_current_user, get_current_workspace, get_system_admin
from domain.ai import AIUsageRecord
from domain.enterprise import (
    AdminActionLog,
    BackgroundJob,
    ComplianceExport,
    OnboardingState,
    QuotaPolicy,
    SubscriptionPlan,
    UsageLedger,
    WorkspaceSubscription,
)
from domain.identity import User, Workspace
from domain.shared import ComplianceExportStatus, JobStatus, SubscriptionStatus

router = APIRouter()


def _to_iso(value):
    return value.isoformat() if value else None


def _ensure_onboarding_state(db: Session, workspace_id: str) -> OnboardingState:
    row = db.query(OnboardingState).filter(OnboardingState.workspace_id == workspace_id).first()
    if row:
        return row
    checklist = {
        "workspace_created": True,
        "brand_setup": False,
        "provider_policy_configured": False,
        "platform_connected": False,
        "first_upload": False,
        "style_profile_created": False,
        "first_publish_ready": False,
    }
    row = OnboardingState(workspace_id=workspace_id, checklist_json=json.dumps(checklist))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _ensure_quota_policy(db: Session, workspace: Workspace) -> QuotaPolicy:
    row = db.query(QuotaPolicy).filter(QuotaPolicy.workspace_id == workspace.id).first()
    if row:
        return row
    row = QuotaPolicy(
        workspace_id=workspace.id,
        storage_quota_mb=workspace.storage_quota_mb,
        retained_footage_days=workspace.raw_retention_days,
        automation_max_mode=(workspace.autonomy_mode.value if hasattr(workspace.autonomy_mode, "value") else str(workspace.autonomy_mode)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
def list_plans(_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == 1).order_by(SubscriptionPlan.monthly_price_usd).all()


@router.get("/subscription", response_model=WorkspaceSubscriptionResponse)
def get_subscription(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    row = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == workspace.id).first()
    if not row:
        raise HTTPException(404, "Workspace subscription not found")
    return WorkspaceSubscriptionResponse(
        id=row.id,
        workspace_id=row.workspace_id,
        plan_id=row.plan_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        billing_email=row.billing_email,
        current_period_start=_to_iso(row.current_period_start),
        current_period_end=_to_iso(row.current_period_end),
        cancel_at=_to_iso(row.cancel_at),
        metadata_json=row.metadata_json,
    )


@router.put("/subscription", response_model=WorkspaceSubscriptionResponse)
def update_subscription(
    body: WorkspaceSubscriptionUpdate,
    workspace=Depends(get_current_workspace),
    _admin=Depends(get_system_admin),
    db: Session = Depends(get_db),
):
    row = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == workspace.id).first()
    if not row:
        raise HTTPException(404, "Workspace subscription not found")
    if body.plan_key:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.key == body.plan_key).first()
        if not plan:
            raise HTTPException(404, "Plan not found")
        row.plan_id = plan.id
        workspace.plan_tier = plan.key
    if body.status is not None:
        row.status = SubscriptionStatus(body.status)
    if body.billing_email is not None:
        row.billing_email = body.billing_email
    db.commit()
    db.refresh(row)
    return WorkspaceSubscriptionResponse(
        id=row.id,
        workspace_id=row.workspace_id,
        plan_id=row.plan_id,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        billing_email=row.billing_email,
        current_period_start=_to_iso(row.current_period_start),
        current_period_end=_to_iso(row.current_period_end),
        cancel_at=_to_iso(row.cancel_at),
        metadata_json=row.metadata_json,
    )


@router.get("/usage", response_model=list[UsageLedgerResponse])
def list_usage(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    rows = db.query(UsageLedger).filter(UsageLedger.workspace_id == workspace.id).order_by(UsageLedger.created_at.desc()).limit(200).all()
    return rows


@router.get("/quota", response_model=QuotaStatusResponse)
def get_quota_status(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    quota = _ensure_quota_policy(db, workspace)
    usage_totals: dict[str, float] = {}
    for category, total in db.query(UsageLedger.category, func.sum(UsageLedger.quantity)).filter(
        UsageLedger.workspace_id == workspace.id
    ).group_by(UsageLedger.category).all():
        usage_totals[str(category)] = float(total or 0.0)
    ai_spend = db.query(func.sum(AIUsageRecord.cost_estimate)).filter(AIUsageRecord.workspace_id == workspace.id).scalar() or 0.0
    usage_totals["ai_spend_usd"] = float(ai_spend)
    exceeded: list[str] = []
    if usage_totals.get("storage_mb", 0.0) > quota.storage_quota_mb:
        exceeded.append("storage_mb")
    if usage_totals.get("render_minutes", 0.0) > quota.render_minutes_quota:
        exceeded.append("render_minutes")
    if usage_totals.get("ai_spend_usd", 0.0) > quota.ai_spend_cap_usd:
        exceeded.append("ai_spend_usd")
    return QuotaStatusResponse(
        quota=QuotaPolicyResponse.model_validate(quota),
        usage=usage_totals,
        exceeded=exceeded,
    )


@router.get("/onboarding", response_model=OnboardingStateResponse)
def get_onboarding(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    row = _ensure_onboarding_state(db, workspace.id)
    return OnboardingStateResponse(
        workspace_id=row.workspace_id,
        checklist_json=row.checklist_json,
        completed_at=_to_iso(row.completed_at),
    )


@router.post("/compliance-exports", response_model=ComplianceExportResponse)
def create_compliance_export(
    body: ComplianceExportCreate,
    workspace=Depends(get_current_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    export = ComplianceExport(
        workspace_id=workspace.id,
        requested_by_user_id=user.id,
        export_type=body.export_type,
        status=ComplianceExportStatus.REQUESTED,
        filters_json=json.dumps(body.filters or {}),
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    job = BackgroundJob(
        workspace_id=workspace.id,
        job_type="compliance_export",
        status=JobStatus.PENDING,
        correlation_id=export.id,
        idempotency_key=f"compliance_export:{export.id}",
        payload_json=json.dumps({"export_id": export.id, "workspace_id": workspace.id}),
    )
    db.add(job)
    db.commit()
    return ComplianceExportResponse(
        id=export.id,
        export_type=export.export_type,
        status=export.status.value if hasattr(export.status, "value") else str(export.status),
        storage_uri=export.storage_uri,
        filters_json=export.filters_json,
        completed_at=_to_iso(export.completed_at),
    )


@router.get("/compliance-exports", response_model=list[ComplianceExportResponse])
def list_compliance_exports(workspace=Depends(get_current_workspace), db: Session = Depends(get_db)):
    rows = db.query(ComplianceExport).filter(ComplianceExport.workspace_id == workspace.id).order_by(ComplianceExport.created_at.desc()).all()
    return [
        ComplianceExportResponse(
            id=row.id,
            export_type=row.export_type,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            storage_uri=row.storage_uri,
            filters_json=row.filters_json,
            completed_at=_to_iso(row.completed_at),
        )
        for row in rows
    ]


@router.get("/admin/summary", response_model=AdminSummaryResponse)
def admin_summary(_admin=Depends(get_system_admin), db: Session = Depends(get_db)):
    return AdminSummaryResponse(
        workspaces=db.query(Workspace).count(),
        users=db.query(User).count(),
        active_subscriptions=db.query(WorkspaceSubscription).filter(WorkspaceSubscription.status.in_(["active", "trial", "grace_period"])).count(),
        queued_jobs=db.query(BackgroundJob).filter(BackgroundJob.status.in_(["pending", "running"])).count(),
        failed_jobs=db.query(BackgroundJob).filter(BackgroundJob.status.in_(["failed", "dead_letter"])).count(),
        pending_exports=db.query(ComplianceExport).filter(ComplianceExport.status.in_(["requested", "processing"])).count(),
        ai_spend_usd=float(db.query(func.sum(AIUsageRecord.cost_estimate)).scalar() or 0.0),
    )


@router.get("/admin/jobs")
def admin_jobs(_admin=Depends(get_system_admin), db: Session = Depends(get_db)):
    rows = db.query(BackgroundJob).order_by(BackgroundJob.created_at.desc()).limit(200).all()
    return {
        "jobs": [
            {
                "id": row.id,
                "workspace_id": row.workspace_id,
                "job_type": row.job_type,
                "status": row.status.value if hasattr(row.status, "value") else str(row.status),
                "correlation_id": row.correlation_id,
                "attempts": row.attempts,
                "last_error": row.last_error,
                "next_attempt_at": _to_iso(row.next_attempt_at),
                "created_at": _to_iso(row.created_at),
            }
            for row in rows
        ]
    }


@router.get("/admin/actions")
def admin_actions(_admin=Depends(get_system_admin), db: Session = Depends(get_db)):
    rows = db.query(AdminActionLog).order_by(AdminActionLog.created_at.desc()).limit(100).all()
    return {
        "actions": [
            {
                "id": row.id,
                "admin_user_id": row.admin_user_id,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "reason": row.reason,
                "metadata_json": row.metadata_json,
                "created_at": _to_iso(row.created_at),
            }
            for row in rows
        ]
    }
