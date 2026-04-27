"""Poll recent comments + DMs and auto-reply using Gemini.

Strategy:
- Scan the last N posted media for new comments.
- For each unreplied comment, classify + generate a reply (or skip/block for spam).
- Same for recent DM conversations (last 24h window due to Messenger policy).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from rich import print as rprint
from tenacity import retry, stop_after_attempt, wait_exponential

from . import graph
from .config import ig_env, load_ig_config
from .state import (
    has_replied_comment,
    has_replied_message,
    list_posted_media_ids,
    record_comment_reply,
    record_message_reply,
)

TONE_GUIDES = {
    "friendly": "Warm, enthusiastic, emoji-friendly. Short (under 15 words).",
    "casual": "Low-effort and brief. 1-5 words, lowercase is fine.",
    "helpful": "Informative. If they asked a question, answer it in one concise sentence.",
    "hybrid": (
        "Adaptive: if the message is a question, answer helpfully in one sentence. "
        "If it's a compliment, thank them warmly. If it's generic/noise, a short "
        "friendly ack."
    ),
}


SYSTEM = """You are a friendly Instagram creator replying to a comment or DM
from a fan. You are in the miniature / ASMR / satisfying-art niche.

Return STRICT JSON:
{
  "action": "reply" | "ignore",
  "reason": "<short reason for ignore, or empty>",
  "text":   "<the reply text>"
}

Ignore rules (action=ignore):
- Spam / scams / promotional links
- Abuse / harassment / offensive
- Clearly automated (emoji-only floods, cyrillic follow-4-follow, etc.)
- Empty or nonsensical

Reply rules:
- Under 200 characters.
- Match the requested tone.
- Sound human. No marketing speak. No 'thanks for your comment'.
- Never claim to be AI.
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _classify_and_reply(message_text: str, kind: str) -> dict[str, Any]:
    import google.generativeai as genai

    key = ig_env().gemini_api_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    cfg = load_ig_config()
    tone_guide = TONE_GUIDES.get(cfg.reply_tone, TONE_GUIDES["hybrid"])

    user = (
        f"Incoming {kind}: {message_text!r}\n"
        f"Tone: {cfg.reply_tone}\n"
        f"Tone guide: {tone_guide}\n"
        f"Spam block keywords: {cfg.spam_block_keywords}"
    )

    genai.configure(api_key=key)
    m = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM,
        generation_config={"temperature": 0.6, "response_mime_type": "application/json"},
    )
    resp = m.generate_content(user)
    text = (resp.text or "{}").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _is_blocked(text: str) -> bool:
    t = (text or "").lower()
    for kw in load_ig_config().spam_block_keywords:
        if kw.lower() in t:
            return True
    return False


def _ts_within(ts: str | None, hours: int) -> bool:
    if not ts:
        return True
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return True
    return when >= datetime.now(timezone.utc) - timedelta(hours=hours)


# ---------- Comments ----------

def process_comments(max_media: int = 10, dry_run: bool = False) -> int:
    """Poll comments on recent posts and reply. Returns number of replies sent."""
    cfg = load_ig_config()
    if not cfg.reply_to_comments:
        return 0

    ids = list_posted_media_ids()[:max_media]
    if not ids:
        ids = [m["id"] for m in graph.list_recent_media(limit=max_media)]

    sent = 0
    for media_id in ids:
        try:
            comments = graph.list_comments(media_id)
        except Exception as e:
            rprint(f"[yellow]Could not list comments on {media_id}: {e}[/yellow]")
            continue
        for c in comments:
            cid = c["id"]
            text = c.get("text", "")
            ts = c.get("timestamp")
            if has_replied_comment(cid):
                continue
            if not _ts_within(ts, cfg.reply_max_age_hours):
                continue
            if _is_blocked(text):
                rprint(f"[yellow]Skipping blocked comment:[/yellow] {text!r}")
                record_comment_reply(cid, media_id, "[BLOCKED]")
                continue
            decision = _classify_and_reply(text, kind="comment")
            if decision.get("action") != "reply":
                rprint(f"[dim]Ignoring comment ({decision.get('reason','')}): {text!r}[/dim]")
                record_comment_reply(cid, media_id, f"[IGNORED] {decision.get('reason','')}")
                continue
            reply = decision.get("text", "").strip()
            if not reply:
                continue
            rprint(f"[cyan]-> replying to comment {cid}:[/cyan] {reply}")
            if not dry_run:
                try:
                    graph.reply_to_comment(cid, reply)
                except Exception as e:
                    rprint(f"[red]Failed to reply to {cid}:[/red] {e}")
                    continue
                record_comment_reply(cid, media_id, reply)
            sent += 1
    return sent


# ---------- DMs ----------

def process_dms(max_convos: int = 20, dry_run: bool = False) -> int:
    cfg = load_ig_config()
    if not cfg.reply_to_dms:
        return 0

    try:
        convos = graph.list_conversations(limit=max_convos)
    except Exception as e:
        rprint(f"[yellow]Could not list conversations: {e}[/yellow]")
        return 0

    sent = 0
    my_id = ig_env().ig_user_id
    for convo in convos:
        cid = convo["id"]
        try:
            msgs = graph.list_messages(cid)
        except Exception as e:
            rprint(f"[yellow]Could not load convo {cid}: {e}[/yellow]")
            continue
        # Newest first in Graph API; iterate from most recent.
        for msg in msgs:
            mid = msg["id"]
            from_id = msg.get("from", {}).get("id")
            if from_id == my_id:
                # Our own message; stop walking back (replies already happened).
                break
            if has_replied_message(mid):
                break
            text = msg.get("message", "")
            ts = msg.get("created_time")
            if not _ts_within(ts, 24):  # Messenger 24h rule
                break
            if _is_blocked(text):
                rprint(f"[yellow]Skipping blocked DM:[/yellow] {text!r}")
                record_message_reply(mid, from_id or "", "[BLOCKED]")
                continue
            decision = _classify_and_reply(text, kind="DM")
            if decision.get("action") != "reply":
                record_message_reply(mid, from_id or "", f"[IGNORED] {decision.get('reason','')}")
                continue
            reply = decision.get("text", "").strip()
            if not reply or not from_id:
                continue
            rprint(f"[cyan]-> DM reply to {from_id}:[/cyan] {reply}")
            if not dry_run:
                try:
                    graph.send_message(from_id, reply)
                except Exception as e:
                    rprint(f"[red]Failed to send DM to {from_id}:[/red] {e}")
                    continue
                record_message_reply(mid, from_id, reply)
            sent += 1
            break  # Reply to the latest unread from this conversation only.
    return sent
