from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    watch_directory: str


class SubClipResponse(BaseModel):
    id: int
    start_time: float
    end_time: float
    score: float | None
    label: str | None

    class Config:
        from_attributes = True


class ClipResponse(BaseModel):
    id: int
    source_path: str
    processed_path: str | None
    clip_type: str | None
    status: str
    duration: float | None
    transcript: str | None
    error_message: str | None
    sub_clips: list[SubClipResponse]

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: int
    name: str
    watch_directory: str
    clips: list[ClipResponse]

    class Config:
        from_attributes = True


class TimelineItemResponse(BaseModel):
    id: int
    clip_id: int | None
    sub_clip_id: int | None
    position: int
    video_url: str
    duration: float
    start_time: float
    end_time: float
    label: str
    clip_type: str | None

    class Config:
        from_attributes = True


class TimelineItemUpdate(BaseModel):
    clip_id: int | None = None
    sub_clip_id: int | None = None
    position: int


class TimelineUpdate(BaseModel):
    items: list[TimelineItemUpdate]
