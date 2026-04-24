"""Config + environment loading."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Env(BaseSettings):
    """API keys + OAuth credentials pulled from environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")
    fal_key: str | None = Field(default=None, alias="FAL_KEY")
    runway_api_key: str | None = Field(default=None, alias="RUNWAY_API_KEY")

    yt_client_id: str | None = Field(default=None, alias="YT_CLIENT_ID")
    yt_client_secret: str | None = Field(default=None, alias="YT_CLIENT_SECRET")
    yt_refresh_token: str | None = Field(default=None, alias="YT_REFRESH_TOKEN")


class ChannelCfg(BaseModel):
    name: str
    handle: str
    niche: str
    description: str


class StyleCfg(BaseModel):
    tone: str
    voice_description: str
    video_aesthetic: str
    color_palette: list[str]


class ShortCfg(BaseModel):
    target_duration_seconds: int = 38
    resolution: tuple[int, int] = (1080, 1920)
    fps: int = 30
    num_scenes: int = 5
    subtitle_font_size: int = 68
    subtitle_outline: int = 4


class KlingCfg(BaseModel):
    model: str = "fal-ai/kling-video/v1.6/standard/text-to-video"
    duration_seconds: int = 5


class RunwayCfg(BaseModel):
    model: str = "gen3a_turbo"
    duration_seconds: int = 5


class VideoCfg(BaseModel):
    provider: str = "kling"
    kling: KlingCfg = KlingCfg()
    runway: RunwayCfg = RunwayCfg()


class TTSCfg(BaseModel):
    provider: str = "edge"
    # ElevenLabs voice_id OR edge-tts voice name OR OpenAI voice; read by the adapter.
    voice_id: str = "en-US-AriaNeural"
    model: str = "eleven_turbo_v2_5"


class LLMCfg(BaseModel):
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"


class ProvidersCfg(BaseModel):
    llm: LLMCfg = LLMCfg()
    tts: TTSCfg = TTSCfg()
    video: VideoCfg = VideoCfg()


class UploadCfg(BaseModel):
    enabled: bool = True
    privacy_status: str = "public"
    category_id: str = "22"
    made_for_kids: bool = False
    title_prefix: str = ""
    default_tags: list[str] = []


class CadenceCfg(BaseModel):
    uploads_per_day: int = 1


class MusicCfg(BaseModel):
    bed_volume_db: float = -18
    voiceover_volume_db: float = -3


class Config(BaseModel):
    channel: ChannelCfg
    style: StyleCfg
    short: ShortCfg
    providers: ProvidersCfg
    upload: UploadCfg
    cadence: CadenceCfg
    music: MusicCfg


@lru_cache(maxsize=1)
def load_config(path: str | Path = ROOT / "config.yaml") -> Config:
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return Config(**data)


@lru_cache(maxsize=1)
def env() -> Env:
    return Env()  # type: ignore[call-arg]


def project_root() -> Path:
    return ROOT


def ensure_dirs() -> None:
    for sub in ("data", "outputs", "assets/music", "assets/fonts"):
        (ROOT / sub).mkdir(parents=True, exist_ok=True)
