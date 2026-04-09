import enum
from sqlalchemy import Column, Integer, String, Float, Enum, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from database import Base


class ClipType(str, enum.Enum):
    TALKING = "talking"
    BROLL = "broll"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    TRANSCRIBING = "transcribing"
    CLASSIFYING = "classifying"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    watch_directory = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    clips = relationship("Clip", back_populates="project", cascade="all, delete-orphan")
    timeline_items = relationship("TimelineItem", back_populates="project", cascade="all, delete-orphan")


class Clip(Base):
    __tablename__ = "clips"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    source_path = Column(String, nullable=False)
    processed_path = Column(String, nullable=True)
    clip_type = Column(Enum(ClipType), nullable=True)
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    duration = Column(Float, nullable=True)
    transcript = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="clips")
    sub_clips = relationship("SubClip", back_populates="parent_clip", cascade="all, delete-orphan")


class SubClip(Base):
    __tablename__ = "sub_clips"

    id = Column(Integer, primary_key=True)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    score = Column(Float, nullable=True)
    label = Column(String, nullable=True)

    parent_clip = relationship("Clip", back_populates="sub_clips")


class TimelineItem(Base):
    __tablename__ = "timeline_items"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    clip_id = Column(Integer, ForeignKey("clips.id"), nullable=True)
    sub_clip_id = Column(Integer, ForeignKey("sub_clips.id"), nullable=True)
    position = Column(Integer, nullable=False)

    project = relationship("Project", back_populates="timeline_items")
    clip = relationship("Clip")
    sub_clip = relationship("SubClip")
