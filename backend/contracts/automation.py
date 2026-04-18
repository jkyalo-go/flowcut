from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: str
    category: str
    title: str
    body: str
    read_at: str | None = None
    metadata_json: str | None = None

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: str
    actor: str
    action: str
    target_type: str
    target_id: str | None
    reason: str | None
    metadata_json: str | None = None

    class Config:
        from_attributes = True


class AutonomySettingsResponse(BaseModel):
    workspace_id: str
    project_id: str | None = None
    autonomy_mode: str
    confidence_threshold: float | None = None
    allowed_platforms: list[str] = Field(default_factory=list)
    quiet_hours: str | None = None
    notification_preferences: str | None = None


class AutonomySettingsUpdate(BaseModel):
    autonomy_mode: str
    confidence_threshold: float | None = None
    allowed_platforms: list[str] = Field(default_factory=list)
    quiet_hours: str | None = None
    notification_preferences: str | None = None
    project_id: str | None = None


class ReviewActionRequest(BaseModel):
    action: str
    reason: str | None = None
    corrections: list[dict] = Field(default_factory=list)
    edit_manifest_override: dict | None = None
