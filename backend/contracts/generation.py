from pydantic import BaseModel, Field


class TitleSuggestionsResponse(BaseModel):
    titles: list[str]


class ThumbnailRequest(BaseModel):
    title: str
    skip_indices: list[int] = []


class ThumbnailResponse(BaseModel):
    thumbnail_urls: list[str]


class MetadataRequest(BaseModel):
    title: str
    system_prompt: str | None = None


class DescriptionResponse(BaseModel):
    description: str


class TagsResponse(BaseModel):
    tags: list[str]


class VideoGenerateRequest(BaseModel):
    provider: str
    prompt: str
    output_prefix: str | None = None
    model: str | None = None
    aspect_ratio: str = "16:9"
    image_gcs_uri: str | None = None
    input_video_gcs_uri: str | None = None
    mask_gcs_uri: str | None = None
    mime_type: str | None = None


class VideoTaskResponse(BaseModel):
    provider: str
    model: str
    task_id: str
    status: str
    output_uri: str | None = None
    raw: dict = Field(default_factory=dict)
