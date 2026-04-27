"""Scan content folder, pick next unposted file, post to Instagram."""

from __future__ import annotations

import hashlib
import urllib.parse
from pathlib import Path

from rich import print as rprint

from . import graph
from .captions import compose_final_caption, generate_caption
from .config import ig_env, load_ig_config, project_root
from .state import is_posted, mark_posted

MEDIA_SUFFIXES_IMAGE = {".jpg", ".jpeg", ".png"}
MEDIA_SUFFIXES_VIDEO = {".mp4", ".mov"}
MEDIA_SUFFIXES = MEDIA_SUFFIXES_IMAGE | MEDIA_SUFFIXES_VIDEO


def _content_dir() -> Path:
    return project_root() / load_ig_config().content_dir


def _file_hash(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def discover_next() -> Path | None:
    """Pick the next unposted media file, ordered by filename."""
    root = _content_dir()
    if not root.exists():
        return None
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in MEDIA_SUFFIXES
        and not p.name.startswith(".")
    )
    for p in files:
        rel = p.relative_to(project_root()).as_posix()
        if not is_posted(rel):
            return p
    return None


def _public_url_for(media_path: Path) -> str:
    base = ig_env().public_media_base_url
    if not base:
        raise RuntimeError(
            "PUBLIC_MEDIA_BASE_URL is not set. Instagram Graph API requires a "
            "publicly-accessible HTTPS URL for the media. When running on "
            "GitHub Actions, set this to the raw branch URL, e.g.\n"
            "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/ig_content"
        )
    base = base.rstrip("/")
    cfg = load_ig_config()
    rel_from_content = media_path.relative_to(_content_dir()).as_posix()
    # Percent-encode each path segment but keep slashes
    safe = "/".join(urllib.parse.quote(seg) for seg in rel_from_content.split("/"))
    return f"{base}/{safe}"


def post_next(dry_run: bool = False) -> dict | None:
    """Post the next unposted media. Returns posted record or None if nothing to post."""
    media_path = discover_next()
    if media_path is None:
        rprint("[yellow]No unposted media found in content folder.[/yellow]")
        return None

    rel = media_path.relative_to(project_root()).as_posix()
    rprint(f"[cyan]Posting:[/cyan] {rel}")

    rprint("[cyan]Generating caption with Gemini...[/cyan]")
    caption_data = generate_caption(media_path)
    final_caption = compose_final_caption(caption_data)
    rprint("[green]Caption:[/green]")
    rprint(final_caption)

    if dry_run:
        rprint("[yellow]--dry-run: not posting to Instagram.[/yellow]")
        return {"path": rel, "caption": final_caption, "media_id": None}

    public_url = _public_url_for(media_path)
    rprint(f"[cyan]Public URL:[/cyan] {public_url}")

    suffix = media_path.suffix.lower()
    if suffix in MEDIA_SUFFIXES_VIDEO:
        creation_id = graph.create_reel_container(public_url, final_caption)
        rprint(f"[cyan]Created Reel container:[/cyan] {creation_id}, waiting for processing...")
        graph.wait_until_ready(creation_id)
        media_type = "REELS"
    else:
        creation_id = graph.create_image_container(public_url, final_caption)
        media_type = "IMAGE"

    publish = graph.publish_container(creation_id)
    media_id = publish["id"]
    permalink = graph.get_permalink(media_id)
    rprint(f"[green]Posted![/green] media_id={media_id}  {permalink or ''}")

    mark_posted(
        file_relpath=rel,
        file_hash=_file_hash(media_path),
        media_type=media_type,
        ig_media_id=media_id,
        caption=final_caption,
        permalink=permalink,
    )
    return {
        "path": rel,
        "caption": final_caption,
        "media_id": media_id,
        "permalink": permalink,
    }
