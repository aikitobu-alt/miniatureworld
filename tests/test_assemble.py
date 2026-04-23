"""End-to-end assembly test with synthetic clips (no API calls)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from shorts_pipeline.assemble import assemble
from shorts_pipeline.models import RenderedScene, Scene, Script, Topic


def _make_color_clip(out: Path, color: str, seconds: float, w: int = 1080, h: int = 1920) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color}:s={w}x{h}:d={seconds}:r=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out),
        ],
        check=True, capture_output=True,
    )
    return out


def test_assemble_produces_mp4(tmp_path: Path) -> None:
    topic = Topic(slug="test", headline="test", why_it_works="test", hashtags=["#shorts"])
    scenes = [
        Scene(index=0, description="red", video_prompt="", duration_seconds=2.0, caption="OPEN"),
        Scene(index=1, description="green", video_prompt="", duration_seconds=2.0, caption="MIDDLE"),
        Scene(index=2, description="blue", video_prompt="", duration_seconds=2.0, caption="LOOP"),
    ]
    script = Script(
        topic=topic,
        youtube_title="t",
        youtube_description="d",
        tags=["shorts"],
        voiceover_text="",
        scenes=scenes,
    )
    rendered = []
    for s, c in zip(scenes, ["red", "green", "blue"]):
        path = _make_color_clip(tmp_path / f"scene_{s.index}.mp4", c, s.duration_seconds)
        rendered.append(RenderedScene(scene=s, video_path=path))
    out = assemble(script, rendered, None, tmp_path / "final.mp4")
    assert out.exists()
    assert out.stat().st_size > 1000
