from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TrimAction(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)

    @model_validator(mode="after")
    def end_after_start(self) -> TrimAction:
        if self.end_sec <= self.start_sec:
            raise ValueError(
                f"end_sec ({self.end_sec}) must be greater than start_sec ({self.start_sec})"
            )
        return self


class ZoomAction(BaseModel):
    at_sec: float = Field(ge=0.0)
    factor: float = Field(ge=1.0, le=3.0)
    duration_sec: float = Field(ge=0.05, le=2.0)
    curve: Literal["ease_in", "ease_out", "linear"] = "ease_out"


class TransitionAction(BaseModel):
    at_sec: float = Field(ge=0.0)
    type: Literal["hard_cut", "crossfade", "whip_pan", "zoom_blur"] = "hard_cut"
    duration_sec: float = Field(ge=0.0, le=1.0, default=0.0)

    @model_validator(mode="after")
    def duration_required_for_non_hard_cut(self) -> TransitionAction:
        if self.type != "hard_cut" and self.duration_sec == 0.0:
            raise ValueError(
                f"transition type '{self.type}' requires duration_sec > 0"
            )
        return self


class SFXAction(BaseModel):
    at_sec: float = Field(ge=0.0)
    sfx_id: str = Field(min_length=1)
    volume_db: float = Field(ge=-40.0, le=0.0, default=-12.0)


class CaptionSegment(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    text: str
    animation: Literal["word_by_word", "fade", "slide_up", "typewriter"] = "word_by_word"
    emphasis_words: list[str] = []

    @model_validator(mode="after")
    def end_after_start(self) -> CaptionSegment:
        if self.end_sec <= self.start_sec:
            raise ValueError(
                f"end_sec ({self.end_sec}) must be greater than start_sec ({self.start_sec})"
            )
        return self


class SpeedRamp(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    speed_factor: float = Field(ge=0.25, le=8.0)

    @model_validator(mode="after")
    def end_after_start(self) -> SpeedRamp:
        if self.end_sec <= self.start_sec:
            raise ValueError(
                f"end_sec ({self.end_sec}) must be greater than start_sec ({self.start_sec})"
            )
        return self


Platform = Literal["tiktok", "youtube_shorts", "instagram_reels", "youtube", "linkedin", "x"]


class EditManifest(BaseModel):
    trim: TrimAction
    platform_targets: list[Platform] = Field(min_length=1)
    zooms: list[ZoomAction] = []
    transitions: list[TransitionAction] = []
    sfx: list[SFXAction] = []
    captions: list[CaptionSegment] = []
    speed_ramps: list[SpeedRamp] = []
    music_bed_volume_db: float = Field(ge=-40.0, le=0.0, default=-18.0)
    intro_duration_sec: float = Field(ge=0.0, le=10.0, default=0.0)
    outro_duration_sec: float = Field(ge=0.0, le=10.0, default=2.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1)
