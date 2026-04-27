"""Generate captions + hashtags for a given media file using Gemini.

Uses Gemini's vision capability to understand the image/video content so
captions are grounded in what's actually on screen, not just the filename.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from .config import ig_env, load_ig_config


STYLE_GUIDES = {
    "short": "Punchy 1-2 line caption. Hook first sentence. No fluff.",
    "story": (
        "3-6 short lines forming a mini-story. Start with a hook sentence that "
        "creates curiosity. End with a soft CTA like 'Which one is your favorite?' "
        "or 'Follow for more tiny worlds'. Use 1-3 tasteful emoji."
    ),
    "asmr": "Caption is only emojis (5-10) evoking the sensory feeling. No words.",
    "educational": (
        "Line 1: a surprising fact or number. Line 2: a short explainer. "
        "Line 3: a question inviting a comment. Keep under 200 chars."
    ),
}


SYSTEM = """You are a social-media copywriter for an Instagram creator in the
miniature / ASMR / satisfying-art niche. Write captions that are authentic,
friendly, and optimized for reach.

Rules:
- Never sound like an AI or marketer. Write like the creator.
- Obey the requested style precisely.
- Produce a hashtag list that mixes niche-specific tags (higher intent, lower
  competition) with a few broad ones. Avoid banned/spammy tags. No #followme,
  #follow4follow, #like4like.
- Return STRICT JSON only. No markdown fences.
"""


USER_TEMPLATE = """Style: {style}
Style guide: {style_guide}
Hashtag count: {hashtag_count}
Creator handle: @{handle}
Niche keywords: {niches}

Context about the media (from filename / folder): {filename_context}
{vision_note}

Return JSON:
{{
  "caption":  "<the caption text, newlines allowed, NO hashtags inside>",
  "hashtags": ["#tag1", "#tag2", ...]   // exactly {hashtag_count} tags, all lowercase, with leading #
}}
"""


def _extract_first_frame(video_path: Path) -> Path | None:
    """Pull a representative frame from a video for Gemini vision."""
    try:
        out = video_path.parent / f".{video_path.stem}_frame.jpg"
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-ss", "00:00:01", "-i", str(video_path),
                "-frames:v", "1", "-q:v", "3", str(out),
            ],
            check=True,
        )
        return out if out.exists() else None
    except Exception:
        return None


def _filename_context(path: Path) -> str:
    stem = re.sub(r"[_\-\.]+", " ", path.stem).strip()
    parent = path.parent.name
    return f"filename: '{stem}', folder: '{parent}'"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def generate_caption(media_path: Path) -> dict[str, Any]:
    import google.generativeai as genai

    key = ig_env().gemini_api_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    cfg = load_ig_config()
    style = cfg.caption_style
    style_guide = STYLE_GUIDES.get(style, STYLE_GUIDES["story"])

    user = USER_TEMPLATE.format(
        style=style,
        style_guide=style_guide,
        hashtag_count=cfg.hashtag_count,
        handle=cfg.handle,
        niches=", ".join(cfg.niche_keywords),
        filename_context=_filename_context(media_path),
        vision_note="The attached image/frame shows the media content. Ground your caption in what you see.",
    )

    genai.configure(api_key=key)
    m = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM,
        generation_config={"temperature": 0.85, "response_mime_type": "application/json"},
    )

    parts: list[Any] = [user]
    vision_path: Path | None = None
    suffix = media_path.suffix.lower()
    if suffix in (".mp4", ".mov", ".m4v"):
        vision_path = _extract_first_frame(media_path)
    elif suffix in (".jpg", ".jpeg", ".png", ".webp"):
        vision_path = media_path

    if vision_path and vision_path.exists():
        parts.append(genai.upload_file(str(vision_path)))

    resp = m.generate_content(parts)
    text = (resp.text or "{}").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data: dict[str, Any] = json.loads(text)

    # Normalize hashtags
    tags = [t if t.startswith("#") else f"#{t}" for t in data.get("hashtags", [])]
    tags = [re.sub(r"\s+", "", t).lower() for t in tags]
    data["hashtags"] = tags[: cfg.hashtag_count]
    return data


def compose_final_caption(data: dict[str, Any]) -> str:
    """Join caption + hashtags in the standard Instagram layout."""
    caption = data.get("caption", "").rstrip()
    tags = data.get("hashtags", [])
    if not tags:
        return caption
    return f"{caption}\n.\n.\n.\n{' '.join(tags)}"
