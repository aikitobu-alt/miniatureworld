"""Kling v1.6 via fal.ai - default AI video provider.

Reference: https://fal.ai/models/fal-ai/kling-video/v1.6/standard/text-to-video
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import env, load_config
from ..models import Scene
from .base import SceneProvider


class KlingProvider(SceneProvider):
    name = "kling"

    def __init__(self) -> None:
        key = env().fal_key
        if not key:
            raise RuntimeError("FAL_KEY is not set")
        os.environ["FAL_KEY"] = key  # fal_client reads this

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
    def render(self, scene: Scene, out_path: Path) -> Path:
        import fal_client

        cfg = load_config().providers.video.kling
        duration = int(max(cfg.duration_seconds, min(scene.duration_seconds, 10)))

        result = fal_client.subscribe(
            cfg.model,
            arguments={
                "prompt": scene.video_prompt,
                "duration": str(duration),
                "aspect_ratio": "9:16",
            },
            with_logs=False,
        )
        video_url = result["video"]["url"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", video_url, timeout=120) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return out_path
