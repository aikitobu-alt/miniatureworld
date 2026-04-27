"""Instagram-specific config + env loading."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class IGEnv(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    ig_user_id: str | None = Field(default=None, alias="IG_USER_ID")
    meta_app_id: str | None = Field(default=None, alias="META_APP_ID")
    meta_long_lived_token: str | None = Field(default=None, alias="META_LONG_LIVED_TOKEN")
    public_media_base_url: str | None = Field(
        default=None,
        alias="PUBLIC_MEDIA_BASE_URL",
        description="Public HTTPS base URL where ig_content/ files are served. "
        "When running on GitHub Actions, set this to the raw branch URL, e.g. "
        "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/ig_content",
    )
    webhook_verify_token: str | None = Field(default=None, alias="WEBHOOK_VERIFY_TOKEN")


class InstagramCfg(BaseModel):
    handle: str = "rupsa.chandra"
    content_dir: str = "ig_content"
    caption_style: str = "story"  # short | story | asmr | educational
    reply_tone: str = "hybrid"  # friendly | casual | helpful | hybrid
    hashtag_count: int = 12
    posts_per_day: int = 1
    niche_keywords: list[str] = [
        "miniature",
        "asmr",
        "satisfying",
        "art",
        "diy",
        "tinyworld",
    ]
    # Reply behaviour
    reply_to_comments: bool = True
    reply_to_dms: bool = True
    reply_max_age_hours: int = 48
    spam_block_keywords: list[str] = ["http://", "free followers", "dm me", "telegram"]


@lru_cache(maxsize=1)
def load_ig_config(path: str | Path = ROOT / "config.yaml") -> InstagramCfg:
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}
    raw = data.get("instagram") or {}
    return InstagramCfg(**raw)


@lru_cache(maxsize=1)
def ig_env() -> IGEnv:
    return IGEnv()  # type: ignore[call-arg]


def project_root() -> Path:
    return ROOT
