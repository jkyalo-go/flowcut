from pydantic import BaseModel, Field


class YouTubeUploadRequest(BaseModel):
    title: str
    description: str = ""
    tags: list[str] = []
    category_id: str = "22"
    privacy_status: str = "private"
    thumbnail_index: int | None = None


class PublishRequest(BaseModel):
    title: str
    description: str = ""
    tags: list[str] = []
    privacy_status: str = "private"
    thumbnail_index: int | None = None
    scheduled_at: str | None = None
    platforms: list[str] = Field(default_factory=list)
    render_variants: list[str] = Field(default_factory=lambda: ["default"])
    platform_overrides: dict[str, dict] = Field(default_factory=dict)
    autonomy_override: str | None = None
    idempotency_key: str | None = None


class PlatformConnectionResponse(BaseModel):
    id: str
    platform: str
    account_name: str | None
    account_id: str | None
    token_expiry: str | None = None
    metadata_json: str | None = None

    class Config:
        from_attributes = True


class PlatformConnectionCreate(BaseModel):
    platform: str
    account_name: str | None = None
    account_id: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    metadata_json: str | None = None


class CalendarSlotResponse(BaseModel):
    id: str
    platform: str
    project_id: str | None = None
    clip_id: str | None = None
    render_variant: str | None = None
    scheduled_at: str | None = None
    status: str
    publish_url: str | None = None
    failure_reason: str | None = None
    retry_count: int
    correlation_id: str | None = None
    metadata_json: str | None = None

    class Config:
        from_attributes = True
