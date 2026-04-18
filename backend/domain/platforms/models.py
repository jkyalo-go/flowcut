from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, LargeBinary, String, func
from sqlalchemy.orm import relationship

from database import Base
from domain.shared import ENUM_SQL_OPTIONS, UUID_SQL_TYPE, PlatformType, new_uuid


class PlatformConnection(Base):
    __tablename__ = "platform_connections"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    platform = Column(Enum(PlatformType, **ENUM_SQL_OPTIONS), nullable=False)
    account_name = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    workspace = relationship("Workspace")


class CalendarSlot(Base):
    __tablename__ = "calendar_slots"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=False)
    clip_id = Column(UUID_SQL_TYPE, ForeignKey("clips.id"), nullable=True)
    render_variant = Column(String, nullable=True)
    platform = Column(Enum(PlatformType, **ENUM_SQL_OPTIONS), nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="pending")
    publish_url = Column(String, nullable=True)
    failure_reason = Column(String, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    correlation_id = Column(String, nullable=True)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PlatformAuth(Base):
    """Tracks OAuth tokens for proactive refresh and circuit-breaker integration."""
    __tablename__ = "platform_auth"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    platform = Column(Enum(PlatformType, **ENUM_SQL_OPTIONS), nullable=False)
    access_token_enc = Column(LargeBinary, nullable=True)
    refresh_token_enc = Column(LargeBinary, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="active")
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    workspace = relationship("Workspace")

    __table_args__ = (
        Index("ix_platform_auth_status_expires", "status", "token_expires_at"),
    )


class PlatformAuthState(Base):
    __tablename__ = "platform_auth_states"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    platform = Column(Enum(PlatformType, **ENUM_SQL_OPTIONS), nullable=False)
    state = Column(String, nullable=False, unique=True)
    code_verifier = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
