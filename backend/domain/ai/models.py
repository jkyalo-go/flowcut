from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, LargeBinary, String, func

from database import Base
from domain.shared import ENUM_SQL_OPTIONS, UUID_SQL_TYPE, AIProvider, AIUsageStatus, CredentialSource, new_uuid


class AIProviderCredential(Base):
    __tablename__ = "ai_provider_credentials"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    provider = Column(Enum(AIProvider, **ENUM_SQL_OPTIONS), nullable=False)
    credential_source = Column(Enum(CredentialSource, **ENUM_SQL_OPTIONS), nullable=False, default=CredentialSource.BYOK)
    label = Column(String, nullable=True)
    api_key = Column(String, nullable=True)  # legacy plaintext; new writes use api_key_enc
    api_key_enc = Column(LargeBinary, nullable=True)  # AES-GCM sealed via common.secrets.seal
    allowed_models = Column(String, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    provider = Column(String, nullable=False)
    model_key = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    task_types = Column(String, nullable=False)
    capabilities_json = Column(String, nullable=True)
    enabled = Column(Integer, nullable=False, default=1)
    api_key = Column(String, nullable=True)  # legacy plaintext; new writes use api_key_enc
    api_key_enc = Column(LargeBinary, nullable=True)  # AES-GCM sealed via common.secrets.seal
    base_url = Column(String, nullable=True)
    config_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AIUsageRecord(Base):
    __tablename__ = "ai_usage_records"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=True)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=True)
    clip_id = Column(UUID_SQL_TYPE, ForeignKey("clips.id"), nullable=True)
    task_type = Column(String, nullable=False)
    provider = Column(Enum(AIProvider, **ENUM_SQL_OPTIONS), nullable=False)
    model = Column(String, nullable=False)
    credential_source = Column(Enum(CredentialSource, **ENUM_SQL_OPTIONS), nullable=False)
    request_units = Column(Float, nullable=True)
    response_units = Column(Float, nullable=True)
    cost_estimate = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    status = Column(Enum(AIUsageStatus, **ENUM_SQL_OPTIONS), nullable=False, default=AIUsageStatus.SUCCESS)
    error_message = Column(String, nullable=True)
    correlation_id = Column(String, nullable=False)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
