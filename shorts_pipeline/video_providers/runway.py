"""Runway Gen-3 adapter (premium path).

API docs: https://docs.dev.runwayml.com/api/  (requires API key from https://dev.runwayml.com/)
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import env, load_config
from ..models import Scene
from .base import SceneProvider

BASE = "https://api.dev.runwayml.com/v1"


class RunwayProvider(SceneProvider):
    name = "runway"

    def __init__(self) -> None:
        key = env().runway_api_key
        if not key:
            raise RuntimeError(
                "RUNWAY_API_KEY is not set; set it or switch providers.video.provider in config.yaml"
            )
        self._client = httpx.Client(
            base_url=BASE,
            headers={
                "Authorization": f"Bearer {key}",
                "X-Runway-Version": "2024-11-06",
            },
            timeout=120,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
    def render(self, scene: Scene, out_path: Path) -> Path:
        cfg = load_config().providers.video.runway
        # Runway text_to_video (Gen-3 turbo). For image_to_video, you'd supply promptImage.
        resp = self._client.post(
            "/text_to_video",
            json={
                "model": cfg.model,
                "promptText": scene.video_prompt,
                "ratio": "768:1280",
                "duration": cfg.duration_seconds,
            },
        )
        resp.raise_for_status()
        task_id = resp.json()["id"]
        # Poll
        while True:
            time.sleep(4)
            s = self._client.get(f"/tasks/{task_id}").json()
            status = s.get("status")
            if status in ("SUCCEEDED", "SUCCESS"):
                url = s["output"][0]
                break
            if status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"Runway task failed: {s}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, timeout=180) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return out_path
