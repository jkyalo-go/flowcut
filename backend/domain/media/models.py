from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from database import Base
from domain.shared import ENUM_SQL_OPTIONS, UUID_SQL_TYPE, AssetType, ClipType, ProcessingStatus, ReviewStatus, new_uuid


class Clip(Base):
    __tablename__ = "clips"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=False)
    source_path = Column(String, nullable=False)
    processed_path = Column(String, nullable=True)
    clip_type = Column(Enum(ClipType, **ENUM_SQL_OPTIONS), nullable=True)
    status = Column(Enum(ProcessingStatus, **ENUM_SQL_OPTIONS), default=ProcessingStatus.PENDING)
    review_status = Column(Enum(ReviewStatus, **ENUM_SQL_OPTIONS), default=ReviewStatus.PENDING_REVIEW)
    confidence_score = Column(Float, nullable=True)
    duration = Column(Float, nullable=True)
    recorded_at = Column(DateTime, nullable=True)
    transcript = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    workspace = relationship("Workspace")
    project = relationship("Project", back_populates="clips")
    sub_clips = relationship("SubClip", back_populates="parent_clip", cascade="all, delete-orphan")


class SubClip(Base):
    __tablename__ = "sub_clips"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    clip_id = Column(UUID_SQL_TYPE, ForeignKey("clips.id"), nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    score = Column(Float, nullable=True)
    label = Column(String, nullable=True)

    parent_clip = relationship("Clip", back_populates="sub_clips")


class TimelineItem(Base):
    __tablename__ = "timeline_items"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=False)
    clip_id = Column(UUID_SQL_TYPE, ForeignKey("clips.id"), nullable=True)
    sub_clip_id = Column(UUID_SQL_TYPE, ForeignKey("sub_clips.id"), nullable=True)
    position = Column(Integer, nullable=False)

    project = relationship("Project", back_populates="timeline_items")
    clip = relationship("Clip")
    sub_clip = relationship("SubClip")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    asset_type = Column(Enum(AssetType, **ENUM_SQL_OPTIONS), nullable=False)
    duration = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class MusicItem(Base):
    __tablename__ = "music_items"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=False)
    asset_id = Column(UUID_SQL_TYPE, ForeignKey("assets.id"), nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    volume = Column(Float, default=0.25)

    project = relationship("Project", back_populates="music_items")
    asset = relationship("Asset")


class TitleItem(Base):
    __tablename__ = "title_items"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=False)
    text = Column(String, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)

    project = relationship("Project", back_populates="title_items")


class CaptionItem(Base):
    __tablename__ = "caption_items"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=False)
    text = Column(String, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)

    project = relationship("Project", back_populates="caption_items")


class TimestampItem(Base):
    __tablename__ = "timestamp_items"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=False)
    text = Column(String, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)

    project = relationship("Project", back_populates="timestamp_items")


class TrackerItem(Base):
    __tablename__ = "tracker_items"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    overlay_path = Column(String, nullable=False)

    project = relationship("Project", back_populates="tracker_items")


class SubscribeItem(Base):
    __tablename__ = "subscribe_items"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=False)
    text = Column(String, nullable=False, default="subscribe")
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)

    project = relationship("Project", back_populates="subscribe_items")


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(UUID_SQL_TYPE, primary_key=True, default=new_uuid)
    workspace_id = Column(UUID_SQL_TYPE, ForeignKey("workspaces.id"), nullable=False)
    project_id = Column(UUID_SQL_TYPE, ForeignKey("projects.id"), nullable=True)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    total_size = Column(Integer, nullable=True)
    uploaded_size = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending")
    media_type = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
