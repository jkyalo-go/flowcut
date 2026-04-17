from pydantic import BaseModel

from contracts.media import ClipResponse


class ProjectCreate(BaseModel):
    workspace_id: str
    name: str


class ProjectResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    clips: list[ClipResponse]
    selected_title: str | None = None
    video_description: str | None = None
    video_tags: str | None = None
    video_category: str | None = "22"
    video_visibility: str | None = "private"
    selected_thumbnail_idx: int | None = None
    desc_system_prompt: str | None = None
    thumbnail_urls: str | None = None
    locked_thumbnail_indices: str | None = None
    thumbnail_text: str | None = None
    render_path: str | None = None
    autonomy_mode: str | None = None

    class Config:
        from_attributes = True


class ProjectMetadataUpdate(BaseModel):
    selected_title: str | None = None
    video_description: str | None = None
    video_tags: str | None = None
    video_category: str | None = None
    video_visibility: str | None = None
    selected_thumbnail_idx: int | None = None
    desc_system_prompt: str | None = None
    thumbnail_urls: str | None = None
    locked_thumbnail_indices: str | None = None
    thumbnail_text: str | None = None
    autonomy_mode: str | None = None
    autonomy_policy: str | None = None


class SettingsResponse(BaseModel):
    timezone: str
    workspace_id: str | None = None
    ai_policy: str | None = None


class SettingsUpdate(BaseModel):
    timezone: str | None = None
    workspace_id: str | None = None
    ai_policy: str | None = None
