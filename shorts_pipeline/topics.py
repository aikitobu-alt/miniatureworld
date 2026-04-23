"""Auto-generate fresh topic ideas each run, deduped against prior uploads."""

from __future__ import annotations

import re

from .config import load_config
from .llm import chat_json
from .models import Topic
from .state import record_topic, used_topic_slugs

SYSTEM = """You are a YouTube Shorts topic strategist for a faceless AI-miniature channel.
You MUST return valid JSON only, with the shape:
{"topics":[{"slug":"tiny-honey-harvest","headline":"Tiny honey harvest in a matchbox apiary","why":"curiosity gap + satisfying payoff","hashtags":["#shorts","#miniature"]}, ...]}
Rules:
- Every topic must be visually satisfying, family-safe, <=60s.
- Each headline must follow a H.O.O.K.E.D. pattern: hook word / number / question / superlative / specificity.
- slug is kebab-case, unique, <= 40 chars.
- 2-3 hashtags, all relevant to the specific topic (never unrelated like #automobile).
- Avoid generic templates like "Miniature Farming Tomato"; be specific and curious.
"""


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:40]


def generate_topics(n: int = 10) -> list[Topic]:
    """Generate n fresh topic candidates, excluding ones we've already used."""
    cfg = load_config()
    used = set(used_topic_slugs())
    prompt = (
        f"Channel: {cfg.channel.name} ({cfg.channel.handle})\n"
        f"Niche: {cfg.channel.niche}\n"
        f"Style: {cfg.style.video_aesthetic}\n"
        f"Already-used topic slugs (DO NOT repeat): {sorted(used)[:50]}\n\n"
        f"Generate {n} fresh topic ideas. Favor specificity over generality "
        f"(e.g. 'tiny sugarcane press with syrup drip' beats 'miniature sugarcane'). "
        f"Return the JSON shape exactly."
    )
    data = chat_json(SYSTEM, prompt, temperature=0.9)
    raw = data.get("topics", [])
    topics: list[Topic] = []
    for t in raw:
        slug = _slugify(t.get("slug") or t.get("headline", ""))
        if not slug or slug in used:
            continue
        topics.append(
            Topic(
                slug=slug,
                headline=t.get("headline", slug),
                why_it_works=t.get("why", ""),
                hashtags=[h for h in t.get("hashtags", []) if h][:3],
            )
        )
    for t in topics:
        record_topic(t.slug, t.headline)
    return topics


def pick_next_topic() -> Topic:
    """Return a single fresh topic to use for this run."""
    candidates = generate_topics(10)
    if not candidates:
        raise RuntimeError("No fresh topics generated; tune the prompt or reset state.")
    return candidates[0]
