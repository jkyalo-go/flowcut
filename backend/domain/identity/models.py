from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from database import Base
from domain.shared import AutonomyMode, ENUM_SQL_OPTIONS, UUID_SQL_TYPE, WorkspaceLifecycle, new_uuid


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, nullable=False, unique=True)
    plan_tier = Column(String, nullable=False, default="starter")
    lifecycle_status = Column(Enum(WorkspaceLifecycle, **ENUM_SQL_OPTIONS), nullable=False, default=WorkspaceLifecycle.TRIAL)
    storage_quota_mb = Column(Integer, nullable=False, default=10240)
    raw_retention_days = Column(Integer, nullable=False, default=30)
    autonomy_mode = Column(Enum(AutonomyMode, **ENUM_SQL_OPTIONS), default=AutonomyMode.SUPERVISED)
    autonomy_confidence_threshold = Column(Float, default=0.8)
    autopublish_platforms = Column(String, nullable=True)
    quiet_hours = Column(String, nullable=True)
    notification_preferences = Column(String, nullable=True)
    ai_policy = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    email = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    user_type = Column(String, nullable=False, default="user")
    oauth_provider = Column(String, nullable=True)   # 'google', 'discord', 'twitch'
    oauth_id = Column(String, nullable=True)         # provider's user ID
    avatar_url = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __mapper_args__ = {
        "polymorphic_on": user_type,
        "polymorphic_identity": "user",
    }


class AdminUser(User):
    __mapper_args__ = {
        "polymorphic_identity": "admin",
    }


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False, default="owner")
    created_at = Column(DateTime, server_default=func.now())

    workspace = relationship("Workspace")
    user = relationship("User")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    user_id = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    token = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User")
    workspace = relationship("Workspace")


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    invited_by = Column(UUID_SQL_TYPE, ForeignKey("users.id"), nullable=False)
    email = Column(String, nullable=False)
    role = Column(String, nullable=False, default="editor")
    token = Column(String, nullable=False, unique=True)
    status = Column(String, nullable=False, default="pending")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
