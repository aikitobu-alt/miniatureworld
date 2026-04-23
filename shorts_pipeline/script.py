"""Topic -> structured Script (hook, body, CTA, scene prompts, captions, title, tags)."""

from __future__ import annotations

from .config import load_config
from .llm import chat_json
from .models import Scene, Script, Topic

SYSTEM = """You write viral YouTube Shorts scripts for a faceless AI-miniature channel.
Return JSON ONLY with this exact shape:
{
  "youtube_title": "string (<= 90 chars, H.O.O.K.E.D. formula: hook/number/question/superlative/specificity; no clickbait lies)",
  "youtube_description": "string (2-4 lines, ends with a soft CTA to subscribe; include 2-3 relevant hashtags on the last line)",
  "tags": ["lowercase-tag", ...],
  "voiceover_text": "string (full narration, punctuated naturally, ~70-100 words, whisper-ASMR friendly; include a 2-second hook line first)",
  "scenes": [
    {"description": "human readable", "video_prompt": "rich visual prompt for an AI video model, includes subject, camera, lighting, motion, aesthetic", "duration_seconds": number, "caption": "on-screen text, <= 6 words"}
  ]
}
Hard rules:
- scenes MUST contain exactly num_scenes entries.
- Sum of scene.duration_seconds MUST equal target_duration_seconds.
- First scene MUST open on dramatic motion in frame 1 (water flowing, machine starting, hand entering, crop being harvested). Never a static wide shot.
- Video prompts MUST specify 9:16 vertical, tilt-shift miniature, photoreal, shallow DOF, golden-hour soft light (unless scene demands otherwise).
- Captions: punchy, kinetic, complement voiceover (not duplicate it verbatim).
- Tags: all relevant to THIS specific topic; NEVER include irrelevant tags like "automobile"; include "shorts" and "miniature".
- Final scene should loop back visually to the first (last frame resembles first frame) so YouTube counts replays.
"""


def write_script(topic: Topic) -> Script:
    cfg = load_config()
    user = (
        f"Topic: {topic.headline}\n"
        f"Topic slug: {topic.slug}\n"
        f"Channel: {cfg.channel.name} ({cfg.channel.handle})\n"
        f"Niche: {cfg.channel.niche}\n"
        f"Voice description: {cfg.style.voice_description}\n"
        f"Aesthetic: {cfg.style.video_aesthetic}\n"
        f"num_scenes: {cfg.short.num_scenes}\n"
        f"target_duration_seconds: {cfg.short.target_duration_seconds}\n"
        f"Preferred hashtags on channel: {', '.join(topic.hashtags)}\n"
    )
    data = chat_json(SYSTEM, user, temperature=0.8)
    raw_scenes = data.get("scenes", [])
    scenes = [
        Scene(
            index=i,
            description=s.get("description", ""),
            video_prompt=s.get("video_prompt", ""),
            duration_seconds=float(s.get("duration_seconds", 0)),
            caption=s.get("caption", ""),
        )
        for i, s in enumerate(raw_scenes)
    ]
    # Normalize durations to hit target exactly.
    total = sum(s.duration_seconds for s in scenes) or 1.0
    scale = cfg.short.target_duration_seconds / total
    for s in scenes:
        s.duration_seconds = round(s.duration_seconds * scale, 2)

    return Script(
        topic=topic,
        youtube_title=data.get("youtube_title", topic.headline)[:100],
        youtube_description=data.get("youtube_description", ""),
        tags=[t.lower().lstrip("#") for t in data.get("tags", []) if t][:15],
        voiceover_text=data.get("voiceover_text", ""),
        scenes=scenes,
    )
