from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint, func

from database import Base
from domain.shared import UUID_SQL_TYPE, new_uuid


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=True)
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(String, nullable=False)
    read_at = Column(DateTime, nullable=True)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=True)
    actor = Column(String, nullable=False, default="system")
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    token = Column(String, nullable=False)
    platform = Column(String, nullable=False, default="web")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "token", name="uq_device_token_user"),)
