"""Typer CLI: `shorts <command>`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print as rprint

from .config import env, load_config
from .pipeline import generate_only, run_once
from .topics import generate_topics

app = typer.Typer(help="AI YouTube Shorts pipeline.", no_args_is_help=True)


@app.command()
def check() -> None:
    """Verify config + required API keys are set for the selected providers."""
    cfg = load_config()
    e = env()
    issues: list[str] = []

    llm = cfg.providers.llm.provider
    if llm == "openai" and not e.openai_api_key:
        issues.append("OPENAI_API_KEY missing (LLM provider=openai)")
    if llm == "gemini" and not e.gemini_api_key:
        issues.append("GEMINI_API_KEY missing (LLM provider=gemini)")

    tts = cfg.providers.tts.provider
    if tts == "elevenlabs" and not e.elevenlabs_api_key:
        issues.append("ELEVENLABS_API_KEY missing (TTS provider=elevenlabs)")
    if tts == "openai" and not e.openai_api_key:
        issues.append("OPENAI_API_KEY missing (TTS provider=openai)")
    # tts=edge and tts=none need no key.

    vp = cfg.providers.video.provider
    if vp == "kling" and not e.fal_key:
        issues.append("FAL_KEY missing (video provider=kling)")
    if vp == "runway" and not e.runway_api_key:
        issues.append("RUNWAY_API_KEY missing (video provider=runway)")
    if vp == "stills" and not e.openai_api_key:
        issues.append("OPENAI_API_KEY missing (video provider=stills)")
    # vp=pollinations needs no key.

    if cfg.upload.enabled and not all(
        [e.yt_client_id, e.yt_client_secret, e.yt_refresh_token]
    ):
        issues.append(
            "YouTube OAuth not configured: set YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN"
        )

    if issues:
        rprint("[yellow]Config issues:[/yellow]")
        for i in issues:
            rprint(f"  - {i}")
        raise typer.Exit(code=1)
    rprint("[green]All good.[/green]")


@app.command()
def topics(n: int = 10) -> None:
    """Generate N fresh topic candidates and print them."""
    ts = generate_topics(n)
    rprint(json.dumps([t.model_dump() for t in ts], indent=2))


@app.command()
def generate(no_tts: bool = typer.Option(False, help="Skip voiceover for this run.")) -> None:
    """Generate a Short end-to-end but do NOT upload."""
    if no_tts:
        # Monkey-patch config at runtime
        cfg = load_config()
        cfg.providers.tts.provider = "none"
    short = generate_only()
    rprint(f"[green]Done:[/green] {short.final_mp4}")


@app.command()
def run(no_upload: bool = typer.Option(False, help="Generate only, skip upload.")) -> None:
    """Generate and upload a Short."""
    _short, result = run_once(upload=not no_upload)
    if result:
        rprint(f"[green]Uploaded:[/green] {result.url}")


@app.command()
def assemble_only(script_json: Path, scenes_dir: Path, voiceover: Path | None = None) -> None:
    """Re-assemble a short from an existing script.json + scene_*.mp4 files (for iteration)."""
    from .assemble import assemble
    from .models import RenderedScene, Script

    script = Script.model_validate_json(script_json.read_text())
    rendered = [
        RenderedScene(scene=s, video_path=scenes_dir / f"scene_{s.index:02d}.mp4")
        for s in script.scenes
    ]
    out = scenes_dir / "final.mp4"
    assemble(script, rendered, voiceover, out)
    rprint(f"[green]Wrote:[/green] {out}")


@app.command()
def oauth(
    client_id: str = typer.Option(..., "--client-id", help="Google OAuth Client ID"),
    client_secret: str = typer.Option(..., "--client-secret", help="Google OAuth Client Secret"),
) -> None:
    """Interactive YouTube OAuth flow. Prints the refresh_token to save as YT_REFRESH_TOKEN."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(
        client_config, scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    rprint("[green]Success![/green] Save these as environment variables (or GitHub Actions secrets):")
    rprint(f"  YT_CLIENT_ID={client_id}")
    rprint(f"  YT_CLIENT_SECRET={client_secret}")
    rprint(f"  YT_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    app()
