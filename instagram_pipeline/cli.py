"""Typer CLI: `igbot <command>`."""

from __future__ import annotations

import typer
from rich import print as rprint

from .config import ig_env, load_ig_config
from .poster import discover_next, post_next
from .replier import process_comments, process_dms

app = typer.Typer(help="Instagram auto-posting + DM/comment auto-reply.", no_args_is_help=True)


@app.command()
def check() -> None:
    """Verify config + required keys are set."""
    e = ig_env()
    cfg = load_ig_config()
    issues: list[str] = []
    if not e.gemini_api_key:
        issues.append("GEMINI_API_KEY missing")
    if not e.ig_user_id:
        issues.append("IG_USER_ID missing (Instagram Business Account ID)")
    if not e.meta_app_id:
        issues.append("META_APP_ID missing")
    if not e.meta_long_lived_token:
        issues.append("META_LONG_LIVED_TOKEN missing")
    if not e.public_media_base_url:
        issues.append(
            "PUBLIC_MEDIA_BASE_URL missing (needed for real posts). "
            "For GitHub Actions use: https://raw.githubusercontent.com/<owner>/<repo>/<branch>/ig_content"
        )
    rprint(f"Handle:         @{cfg.handle}")
    rprint(f"Caption style:  {cfg.caption_style}")
    rprint(f"Reply tone:     {cfg.reply_tone}")
    rprint(f"Posts per day:  {cfg.posts_per_day}")
    if issues:
        rprint("[yellow]Issues:[/yellow]")
        for i in issues:
            rprint(f"  - {i}")
        raise typer.Exit(code=1)
    rprint("[green]All good.[/green]")


@app.command()
def next_file() -> None:
    """Show the next unposted media file without posting it."""
    p = discover_next()
    if p:
        rprint(f"[green]Next:[/green] {p}")
    else:
        rprint("[yellow]No unposted media found.[/yellow]")


@app.command()
def post(dry_run: bool = typer.Option(False, "--dry-run", help="Generate caption but do not post.")) -> None:
    """Post the next unposted media file (or dry-run the caption)."""
    post_next(dry_run=dry_run)


@app.command()
def reply(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show replies without sending."),
    comments: bool = typer.Option(True, help="Reply to comments."),
    dms: bool = typer.Option(True, help="Reply to DMs."),
) -> None:
    """Poll recent comments + DMs and auto-reply."""
    e = ig_env()
    if not (e.meta_long_lived_token and e.ig_user_id):
        rprint("[red]Missing META_LONG_LIVED_TOKEN or IG_USER_ID.[/red] Run `igbot check`.")
        raise typer.Exit(code=1)
    total = 0
    if comments:
        total += process_comments(dry_run=dry_run)
    if dms:
        total += process_dms(dry_run=dry_run)
    rprint(f"[green]Replies sent:[/green] {total}")


@app.command()
def daily(
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Daily job: post one item, then poll + reply to recent comments/DMs."""
    rprint("[bold cyan]== Daily IG job ==[/bold cyan]")
    post_next(dry_run=dry_run)
    process_comments(dry_run=dry_run)
    process_dms(dry_run=dry_run)


@app.command()
def token_info() -> None:
    """Diagnose the Meta long-lived token (expiry, scopes)."""
    import httpx
    e = ig_env()
    if not e.meta_long_lived_token or not e.meta_app_id:
        raise typer.Exit(code=1)
    r = httpx.get(
        "https://graph.facebook.com/debug_token",
        params={
            "input_token": e.meta_long_lived_token,
            "access_token": e.meta_long_lived_token,
        },
        timeout=30,
    )
    rprint(r.json())


if __name__ == "__main__":
    app()
