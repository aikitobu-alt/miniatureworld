"""Pydantic data models passed between pipeline stages."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Topic(BaseModel):
    slug: str
    headline: str          # internal "what is this short about"
    why_it_works: str      # one-line justification (good for logs)
    hashtags: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    index: int
    description: str       # human-readable, for logs
    video_prompt: str      # prompt sent to Kling/Runway
    duration_seconds: float
    caption: str           # on-screen text, short (<= 6 words)


class Script(BaseModel):
    topic: Topic
    youtube_title: str     # H.O.O.K.E.D. formula
    youtube_description: str
    tags: list[str]
    voiceover_text: str    # full narration, punctuated for TTS
    scenes: list[Scene]

    @property
    def total_duration(self) -> float:
        return sum(s.duration_seconds for s in self.scenes)


class RenderedScene(BaseModel):
    scene: Scene
    video_path: Path

    model_config = {"arbitrary_types_allowed": True}


class RenderedShort(BaseModel):
    script: Script
    scenes: list[RenderedScene]
    voiceover_path: Path | None
    final_mp4: Path
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"arbitrary_types_allowed": True}


class UploadResult(BaseModel):
    video_id: str
    url: str
    raw: dict[str, Any] = Field(default_factory=dict)
