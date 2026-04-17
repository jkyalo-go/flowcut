from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from database import Base
from domain.shared import AutonomyMode, ENUM_SQL_OPTIONS, IntakeMode, UUID_SQL_TYPE, new_uuid


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String, nullable=False)
    watch_directory = Column(String, nullable=True)
    intake_mode = Column(Enum(IntakeMode, **ENUM_SQL_OPTIONS), nullable=False, default=IntakeMode.WATCH)
    source_type = Column(String, nullable=True)
    storage_prefix = Column(String, nullable=True)
    autonomy_mode = Column(Enum(AutonomyMode, **ENUM_SQL_OPTIONS), nullable=True)
    autonomy_policy = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    selected_title = Column(String, nullable=True)
    video_description = Column(String, nullable=True)
    video_tags = Column(String, nullable=True)
    video_category = Column(String, default="22")
    video_visibility = Column(String, default="private")
    selected_thumbnail_idx = Column(Integer, nullable=True)
    desc_system_prompt = Column(String, nullable=True)
    thumbnail_urls = Column(String, nullable=True)
    locked_thumbnail_indices = Column(String, nullable=True)
    thumbnail_text = Column(String, nullable=True)
    render_path = Column(String, nullable=True)

    workspace = relationship("Workspace")
    clips = relationship("Clip", back_populates="project", cascade="all, delete-orphan")
    timeline_items = relationship("TimelineItem", back_populates="project", cascade="all, delete-orphan")
    music_items = relationship("MusicItem", back_populates="project", cascade="all, delete-orphan")
    title_items = relationship("TitleItem", back_populates="project", cascade="all, delete-orphan")
    caption_items = relationship("CaptionItem", back_populates="project", cascade="all, delete-orphan")
    timestamp_items = relationship("TimestampItem", back_populates="project", cascade="all, delete-orphan")
    tracker_items = relationship("TrackerItem", back_populates="project", cascade="all, delete-orphan")
    subscribe_items = relationship("SubscribeItem", back_populates="project", cascade="all, delete-orphan")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_app_settings_workspace_key"),
    )


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=True)
    name = Column(String, nullable=False)
    brand_kit = Column(String, nullable=True)
    platform_targets = Column(String, nullable=True)
    preferences = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
