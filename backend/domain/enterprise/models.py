from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, func

from database import Base
from domain.shared import (
    ComplianceExportStatus,
    ENUM_SQL_OPTIONS,
    InvoiceStatus,
    JobStatus,
    SubscriptionStatus,
    UUID_SQL_TYPE,
    new_uuid,
)


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    key = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    monthly_price_usd = Column(Float, nullable=False, default=0.0)
    quotas_json = Column(String, nullable=False, default="{}")
    features_json = Column(String, nullable=False, default="{}")
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WorkspaceSubscription(Base):
    __tablename__ = "workspace_subscriptions"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False, unique=True)
    plan_id = Column(UUID_SQL_TYPE, ForeignKey("subscription_plans.id"), nullable=False)
    status = Column(Enum(SubscriptionStatus, **ENUM_SQL_OPTIONS), nullable=False, default=SubscriptionStatus.TRIAL)
    billing_email = Column(String, nullable=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at = Column(DateTime, nullable=True)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    subscription_id = Column(UUID_SQL_TYPE, ForeignKey("workspace_subscriptions.id"), nullable=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    amount_usd = Column(Float, nullable=False, default=0.0)
    status = Column(Enum(InvoiceStatus, **ENUM_SQL_OPTIONS), nullable=False, default=InvoiceStatus.DRAFT)
    line_items_json = Column(String, nullable=False, default="[]")
    created_at = Column(DateTime, server_default=func.now())


class UsageLedger(Base):
    __tablename__ = "usage_ledger"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=True)
    user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=True)
    category = Column(String, nullable=False)
    quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String, nullable=False)
    amount_usd = Column(Float, nullable=False, default=0.0)
    correlation_id = Column(String, nullable=False)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class QuotaPolicy(Base):
    __tablename__ = "quota_policies"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False, unique=True)
    storage_quota_mb = Column(Integer, nullable=False, default=10240)
    ai_spend_cap_usd = Column(Float, nullable=False, default=50.0)
    render_minutes_quota = Column(Integer, nullable=False, default=300)
    connected_platforms_quota = Column(Integer, nullable=False, default=2)
    team_seats_quota = Column(Integer, nullable=False, default=1)
    retained_footage_days = Column(Integer, nullable=False, default=30)
    automation_max_mode = Column(String, nullable=False, default="supervised")
    hard_enforcement = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class OnboardingState(Base):
    __tablename__ = "onboarding_states"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False, unique=True)
    checklist_json = Column(String, nullable=False, default="{}")
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ComplianceExport(Base):
    __tablename__ = "compliance_exports"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    requested_by_user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=True)
    export_type = Column(String, nullable=False, default="audit_log")
    status = Column(Enum(ComplianceExportStatus, **ENUM_SQL_OPTIONS), nullable=False, default=ComplianceExportStatus.REQUESTED)
    storage_uri = Column(String, nullable=True)
    filters_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


class AdminActionLog(Base):
    __tablename__ = "admin_action_logs"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    admin_user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=True)
    job_type = Column(String, nullable=False)
    status = Column(Enum(JobStatus, **ENUM_SQL_OPTIONS), nullable=False, default=JobStatus.PENDING)
    correlation_id = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=True, unique=True)
    payload_json = Column(String, nullable=False, default="{}")
    result_json = Column(String, nullable=True)
    next_attempt_at = Column(DateTime, nullable=True)
    lease_owner = Column(String, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
