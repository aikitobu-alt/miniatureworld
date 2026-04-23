"""End-to-end orchestration: topic -> script -> TTS -> scenes -> assemble -> upload."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.console import Console

from .assemble import assemble
from .config import ensure_dirs, load_config, project_root
from .models import RenderedScene, RenderedShort, Script, Topic, UploadResult
from .script import write_script
from .state import mark_topic_used, record_upload
from .topics import pick_next_topic
from .tts import synthesize
from .video_providers import get_provider
from .youtube import upload_short

console = Console()


def _run_dir(slug: str) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    d = project_root() / "outputs" / f"{ts}_{slug}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_only(topic: Topic | None = None) -> RenderedShort:
    """Generate a short end-to-end but do NOT upload."""
    ensure_dirs()
    cfg = load_config()
    console.rule("[bold]Topic")
    topic = topic or pick_next_topic()
    console.print(topic)

    console.rule("[bold]Script")
    script = write_script(topic)
    console.print(json.dumps(script.model_dump(), indent=2, default=str))

    run = _run_dir(topic.slug)
    (run / "script.json").write_text(script.model_dump_json(indent=2))

    console.rule("[bold]Voiceover")
    vo_path = None
    if cfg.providers.tts.provider != "none" and script.voiceover_text.strip():
        vo_path = synthesize(script.voiceover_text, run / "voiceover.mp3")
        console.print(f"voiceover -> {vo_path}")
    else:
        console.print("(TTS disabled)")

    console.rule(f"[bold]Scenes ({cfg.providers.video.provider})")
    provider = get_provider(cfg.providers.video.provider)
    rendered: list[RenderedScene] = []
    for s in script.scenes:
        clip = run / f"scene_{s.index:02d}.mp4"
        console.print(f"  scene {s.index}: {s.description[:80]}")
        provider.render(s, clip)
        rendered.append(RenderedScene(scene=s, video_path=clip))

    console.rule("[bold]Assemble")
    final = assemble(script, rendered, vo_path, run / "final.mp4")
    console.print(f"final -> {final}")

    return RenderedShort(
        script=script,
        scenes=rendered,
        voiceover_path=vo_path,
        final_mp4=final,
    )


def run_once(upload: bool = True) -> tuple[RenderedShort, UploadResult | None]:
    short = generate_only()
    script = short.script
    result: UploadResult | None = None
    if upload and load_config().upload.enabled:
        console.rule("[bold]Upload")
        try:
            result = upload_short(short.final_mp4, script)
            console.print(f"uploaded -> {result.url}")
            record_upload(
                topic_slug=script.topic.slug,
                video_id=result.video_id,
                url=result.url,
                title=script.youtube_title,
                status="uploaded",
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]upload failed:[/red] {exc}")
            record_upload(
                topic_slug=script.topic.slug,
                video_id=None,
                url=None,
                title=script.youtube_title,
                status=f"failed:{exc}",
            )
            raise
    else:
        record_upload(
            topic_slug=script.topic.slug,
            video_id=None,
            url=None,
            title=script.youtube_title,
            status="generated_only",
        )
    mark_topic_used(script.topic.slug)
    return short, result
