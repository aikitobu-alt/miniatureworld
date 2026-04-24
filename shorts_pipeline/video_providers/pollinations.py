"""FREE scene provider: Pollinations.ai image + ffmpeg Ken Burns motion.

Pollinations (https://pollinations.ai/) offers an unauthenticated free image
generation API. We request a 9:16 image per scene and animate it with a slow
zoom-in (Ken Burns) to simulate motion video.

Quality won't match Kling / Runway, but it's $0 and good enough to ship Shorts.
"""

from __future__ import annotations

import hashlib
import random
import subprocess
import urllib.parse
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import load_config
from ..models import Scene
from .base import SceneProvider

BASE = "https://image.pollinations.ai/prompt/"


class PollinationsProvider(SceneProvider):
    name = "pollinations"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _download_image(self, prompt: str, png_path: Path) -> Path:
        # Deterministic-ish seed from prompt so retries don't swing wildly.
        seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16) % (10**9)
        # Small jitter so repeat scenes aren't identical.
        seed = (seed + random.randint(0, 100)) % (10**9)
        params = {
            "width": 1024,
            "height": 1792,
            "nologo": "true",
            "seed": seed,
            "model": "flux",
            "enhance": "true",
        }
        url = BASE + urllib.parse.quote(prompt) + "?" + urllib.parse.urlencode(params)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, timeout=180, follow_redirects=True) as r:
            r.raise_for_status()
            with open(png_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        if png_path.stat().st_size < 2000:
            raise RuntimeError(f"Pollinations returned tiny/empty image for prompt: {prompt[:80]}")
        return png_path

    def render(self, scene: Scene, out_path: Path) -> Path:
        cfg = load_config().short
        w, h = cfg.resolution
        fps = cfg.fps
        png = out_path.with_suffix(".png")
        self._download_image(scene.video_prompt, png)
        total_frames = max(int(scene.duration_seconds * fps), fps)
        # Ken Burns: alternate pan direction per scene index for variety.
        if scene.index % 2 == 0:
            # zoom-in, centered
            zoompan = (
                f"zoompan=z='min(zoom+0.0018,1.20)':d={total_frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}"
            )
        else:
            # zoom-in with slow pan down
            zoompan = (
                f"zoompan=z='min(zoom+0.0015,1.18)':d={total_frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+on*0.4':s={w}x{h}:fps={fps}"
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
