from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class TrimAction(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)


class ZoomAction(BaseModel):
    at_sec: float = Field(ge=0.0)
    factor: float = Field(ge=1.0, le=3.0)
    duration_sec: float = Field(ge=0.05, le=2.0)
    curve: Literal["ease_in", "ease_out", "linear"] = "ease_out"


class TransitionAction(BaseModel):
    at_sec: float = Field(ge=0.0)
    type: Literal["hard_cut", "crossfade", "whip_pan", "zoom_blur"] = "hard_cut"
    duration_sec: float = Field(ge=0.0, le=1.0, default=0.0)


class SFXAction(BaseModel):
    at_sec: float = Field(ge=0.0)
    sfx_id: str
    volume_db: float = Field(ge=-40.0, le=0.0, default=-12.0)


class CaptionSegment(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    text: str
    animation: Literal["word_by_word", "fade", "slide_up", "typewriter"] = "word_by_word"
    emphasis_words: List[str] = []


class SpeedRamp(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    speed_factor: float = Field(ge=0.25, le=8.0)


Platform = Literal["tiktok", "youtube_shorts", "instagram_reels", "youtube", "linkedin", "x"]


class EditManifest(BaseModel):
    trim: TrimAction
    platform_targets: List[Platform]
    zooms: List[ZoomAction] = []
    transitions: List[TransitionAction] = []
    sfx: List[SFXAction] = []
    captions: List[CaptionSegment] = []
    speed_ramps: List[SpeedRamp] = []
    music_bed_volume_db: float = Field(ge=-40.0, le=0.0, default=-18.0)
    intro_duration_sec: float = Field(ge=0.0, le=10.0, default=0.0)
    outro_duration_sec: float = Field(ge=0.0, le=10.0, default=2.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
