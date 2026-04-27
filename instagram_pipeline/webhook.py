"""Meta Webhook receiver for real-time comment + DM events.

Not required for the daily cron (which polls), but enables sub-minute replies.

Run with:  uvicorn instagram_pipeline.webhook:app --host 0.0.0.0 --port 8080

Point your Meta App Webhook to https://<your-public-host>/webhook with the
same verify_token you set in WEBHOOK_VERIFY_TOKEN.
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Request
except ImportError as e:  # pragma: no cover
    raise SystemExit("FastAPI not installed. Run: pip install fastapi uvicorn") from e

from rich import print as rprint

from . import graph
from .config import ig_env
from .replier import _classify_and_reply, _is_blocked  # reuse helpers
from .state import (
    has_replied_comment,
    has_replied_message,
    record_comment_reply,
    record_message_reply,
)

app = FastAPI(title="IG auto-reply webhook")


@app.get("/webhook")
async def verify(request: Request) -> Any:
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    expected = ig_env().webhook_verify_token
    if mode == "subscribe" and expected and token and token == expected:
        return int(challenge or "0")
    raise HTTPException(status_code=403, detail="verify token mismatch")


@app.post("/webhook")
async def receive(request: Request) -> dict[str, str]:
    payload = await request.json()
    try:
        _handle(payload)
    except Exception as e:
        rprint(f"[red]webhook error:[/red] {e}")
    return {"status": "ok"}


def _handle(payload: dict[str, Any]) -> None:
    for entry in payload.get("entry", []):
        # Comment events
        for change in entry.get("changes", []):
            if change.get("field") == "comments":
                value = change.get("value", {}) or {}
                cid = value.get("id")
                text = value.get("text", "")
                media_id = (value.get("media") or {}).get("id") or ""
                if not cid or has_replied_comment(cid) or _is_blocked(text):
                    continue
                decision = _classify_and_reply(text, kind="comment")
                if decision.get("action") == "reply" and decision.get("text"):
                    try:
                        graph.reply_to_comment(cid, decision["text"])
                        record_comment_reply(cid, media_id, decision["text"])
                        rprint(f"[green]Replied comment {cid}[/green]")
                    except Exception as e:
                        rprint(f"[red]reply fail {cid}: {e}[/red]")
        # DM events
        for msg_entry in entry.get("messaging", []):
            sender_id = (msg_entry.get("sender") or {}).get("id")
            msg = msg_entry.get("message") or {}
            mid = msg.get("mid")
            text = msg.get("text", "")
            if not mid or not sender_id or has_replied_message(mid) or _is_blocked(text):
                continue
            decision = _classify_and_reply(text, kind="DM")
            if decision.get("action") == "reply" and decision.get("text"):
                try:
                    graph.send_message(sender_id, decision["text"])
                    record_message_reply(mid, sender_id, decision["text"])
                    rprint(f"[green]Replied DM {mid}[/green]")
                except Exception as e:
                    rprint(f"[red]dm fail {mid}: {e}[/red]")
