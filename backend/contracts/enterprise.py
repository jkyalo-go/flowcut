from pydantic import BaseModel, Field


class SubscriptionPlanResponse(BaseModel):
    id: str
    key: str
    name: str
    monthly_price_usd: float
    quotas_json: str
    features_json: str
    is_active: int

    class Config:
        from_attributes = True


class WorkspaceSubscriptionResponse(BaseModel):
    id: str
    workspace_id: str
    plan_id: str
    status: str
    billing_email: str | None = None
    current_period_start: str | None = None
    current_period_end: str | None = None
    cancel_at: str | None = None
    metadata_json: str | None = None

    class Config:
        from_attributes = True


class UsageLedgerResponse(BaseModel):
    id: str
    category: str
    quantity: float
    unit: str
    amount_usd: float
    correlation_id: str
    metadata_json: str | None = None

    class Config:
        from_attributes = True


class QuotaPolicyResponse(BaseModel):
    workspace_id: str
    storage_quota_mb: int
    ai_spend_cap_usd: float
    render_minutes_quota: int
    connected_platforms_quota: int
    team_seats_quota: int
    retained_footage_days: int
    automation_max_mode: str
    hard_enforcement: int

    class Config:
        from_attributes = True


class QuotaStatusResponse(BaseModel):
    quota: QuotaPolicyResponse
    usage: dict[str, float]
    exceeded: list[str] = Field(default_factory=list)


class OnboardingStateResponse(BaseModel):
    workspace_id: str
    checklist_json: str
    completed_at: str | None = None

    class Config:
        from_attributes = True


class ComplianceExportCreate(BaseModel):
    export_type: str = "audit_log"
    filters: dict | None = None


class ComplianceExportResponse(BaseModel):
    id: str
    export_type: str
    status: str
    storage_uri: str | None = None
    filters_json: str | None = None
    completed_at: str | None = None

    class Config:
        from_attributes = True


class AdminSummaryResponse(BaseModel):
    workspaces: int
    users: int
    active_subscriptions: int
    queued_jobs: int
    failed_jobs: int
    pending_exports: int
    ai_spend_usd: float


class WorkspaceSubscriptionUpdate(BaseModel):
    plan_key: str | None = None
    status: str | None = None
    billing_email: str | None = None

