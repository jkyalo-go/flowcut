from pydantic import BaseModel


class SubClipResponse(BaseModel):
    id: str
    start_time: float
    end_time: float
    score: float | None
    label: str | None

    class Config:
        from_attributes = True


class ClipResponse(BaseModel):
    id: str
    workspace_id: str
    source_path: str
    processed_path: str | None
    clip_type: str | None
    status: str
    review_status: str | None = None
    confidence_score: float | None = None
    duration: float | None
    transcript: str | None
    error_message: str | None
    sub_clips: list[SubClipResponse]

    class Config:
        from_attributes = True


class TimelineItemResponse(BaseModel):
    id: str
    clip_id: str | None
    sub_clip_id: str | None
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
    clip_id: str | None = None
    sub_clip_id: str | None = None
    position: int


class TimelineUpdate(BaseModel):
    items: list[TimelineItemUpdate]


class AssetResponse(BaseModel):
    id: str
    name: str
    file_path: str
    asset_type: str
    duration: float

    class Config:
        from_attributes = True


class MusicItemResponse(BaseModel):
    id: str
    asset_id: str
    asset_name: str
    start_time: float
    end_time: float
    volume: float

    class Config:
        from_attributes = True


class VolumeKeypoint(BaseModel):
    t: float
    v: float


class MusicAutoResponse(BaseModel):
    items: list[MusicItemResponse]
    volume_envelope: list[VolumeKeypoint]


class TitleItemResponse(BaseModel):
    id: str
    text: str
    start_time: float
    end_time: float

    class Config:
        from_attributes = True


class TitleItemUpdate(BaseModel):
    text: str | None = None
    start_time: float | None = None
    end_time: float | None = None


class TitleAutoResponse(BaseModel):
    items: list[TitleItemResponse]


class CaptionItemResponse(BaseModel):
    id: str
    text: str
    start_time: float
    end_time: float

    class Config:
        from_attributes = True


class CaptionItemUpdate(BaseModel):
    text: str | None = None
    start_time: float | None = None
    end_time: float | None = None


class CaptionAutoResponse(BaseModel):
    items: list[CaptionItemResponse]


class TimestampItemResponse(BaseModel):
    id: str
    text: str
    start_time: float
    end_time: float

    class Config:
        from_attributes = True


class TimestampItemUpdate(BaseModel):
    text: str | None = None
    start_time: float | None = None
    end_time: float | None = None


class TimestampAutoResponse(BaseModel):
    items: list[TimestampItemResponse]


class TrackerItemResponse(BaseModel):
    id: str
    start_time: float
    end_time: float
    overlay_url: str

    class Config:
        from_attributes = True


class TrackerAutoResponse(BaseModel):
    items: list[TrackerItemResponse]


class SubscribeItemResponse(BaseModel):
    id: str
    text: str
    start_time: float
    end_time: float

    class Config:
        from_attributes = True


class SubscribeItemUpdate(BaseModel):
    text: str | None = None
    start_time: float | None = None
    end_time: float | None = None


class SubscribeAutoResponse(BaseModel):
    items: list[SubscribeItemResponse]


class RemixAutoResponse(BaseModel):
    items: list[TimelineItemResponse]


class UploadSessionCreate(BaseModel):
    workspace_id: str
    project_id: str | None = None
    filename: str
    total_size: int | None = None
    media_type: str | None = None


class UploadSessionResponse(BaseModel):
    id: str
    workspace_id: str
    project_id: str | None
    filename: str
    storage_path: str
    total_size: int | None
    uploaded_size: int
    status: str
    media_type: str | None = None

    class Config:
        from_attributes = True


class UploadConfirmRequest(BaseModel):
    project_id: str
