"""Cheap fallback provider: AI still image + Ken Burns motion.

Uses OpenAI gpt-image-1 to generate a 9:16 still, then ffmpeg zoompan to animate
it. Costs pennies per scene instead of dollars. Useful for testing or budget runs.
"""

from __future__ import annotations

import base64
import subprocess
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import env, load_config
from ..models import Scene
from .base import SceneProvider


class StillsProvider(SceneProvider):
    name = "stills"

    def __init__(self) -> None:
        key = env().openai_api_key
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _gen_image(self, prompt: str, png_path: Path) -> Path:
        resp = self._client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1536",
            n=1,
        )
        b64 = resp.data[0].b64_json
        assert b64
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(b64))
        return png_path

    def render(self, scene: Scene, out_path: Path) -> Path:
        cfg = load_config().short
        w, h = cfg.resolution
        fps = cfg.fps
        png = out_path.with_suffix(".png")
        self._gen_image(scene.video_prompt, png)
        total_frames = max(int(scene.duration_seconds * fps), fps)
        # Ken Burns: subtle zoom-in
        zoompan = (
            f"zoompan=z='min(zoom+0.0015,1.15)':d={total_frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}"
        )
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", str(png),
            "-vf", zoompan,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", f"{scene.duration_seconds}",
            "-r", str(fps),
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path
