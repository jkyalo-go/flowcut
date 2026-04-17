from pydantic import BaseModel, Field


class AIProviderOption(BaseModel):
    provider: str
    task_types: list[str]
    models: list[str]


class AIProviderConfigResponse(BaseModel):
    id: str
    provider: str
    model_key: str
    display_name: str
    task_types: str
    capabilities_json: str | None = None
    enabled: int
    base_url: str | None = None
    config_json: str | None = None

    class Config:
        from_attributes = True


class AIProviderConfigUpdate(BaseModel):
    display_name: str | None = None
    task_types: list[str] | None = None
    capabilities: dict | None = None
    enabled: bool | None = None
    api_key: str | None = None
    base_url: str | None = None
    config: dict | None = None


class AIProviderCredentialCreate(BaseModel):
    provider: str
    api_key: str
    label: str | None = None
    allowed_models: list[str] = Field(default_factory=list)


class AIProviderCredentialResponse(BaseModel):
    id: str
    provider: str
    credential_source: str
    label: str | None
    allowed_models: str | None
    is_active: int

    class Config:
        from_attributes = True


class AIUsageRecordResponse(BaseModel):
    id: str
    task_type: str
    provider: str
    model: str
    credential_source: str
    request_units: float | None
    response_units: float | None
    cost_estimate: float | None
    latency_ms: float | None
    status: str
    error_message: str | None
    correlation_id: str
    created_at: str | None = None

    class Config:
        from_attributes = True


class AISettingsUpdate(BaseModel):
    default_provider_by_task: dict[str, str] = Field(default_factory=dict)
    allowed_providers: list[str] = Field(default_factory=list)
    spend_cap_usd: float | None = None
    fallback_chains: dict[str, list[str]] = Field(default_factory=dict)
