"""Thin wrapper around the Instagram Graph API (v21.0).

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import ig_env

API = "https://graph.facebook.com/v21.0"


def _token() -> str:
    t = ig_env().meta_long_lived_token
    if not t:
        raise RuntimeError("META_LONG_LIVED_TOKEN is not set")
    return t


def _ig_user_id() -> str:
    uid = ig_env().ig_user_id
    if not uid:
        raise RuntimeError("IG_USER_ID is not set")
    return uid


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _post(path: str, data: dict[str, Any]) -> dict[str, Any]:
    data = {**data, "access_token": _token()}
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{API}{path}", data=data)
        r.raise_for_status()
        return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = {**(params or {}), "access_token": _token()}
    with httpx.Client(timeout=60) as c:
        r = c.get(f"{API}{path}", params=params)
        r.raise_for_status()
        return r.json()


# ---------- Content publishing ----------

def create_image_container(image_url: str, caption: str) -> str:
    """Return creation_id."""
    resp = _post(
        f"/{_ig_user_id()}/media",
        {"image_url": image_url, "caption": caption},
    )
    return resp["id"]


def create_reel_container(video_url: str, caption: str, cover_url: str | None = None) -> str:
    data: dict[str, Any] = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
    }
    if cover_url:
        data["cover_url"] = cover_url
    resp = _post(f"/{_ig_user_id()}/media", data)
    return resp["id"]


def wait_until_ready(creation_id: str, timeout_s: int = 300) -> None:
    """Reels need processing time. Poll status_code until FINISHED."""
    start = time.time()
    while time.time() - start < timeout_s:
        resp = _get(f"/{creation_id}", {"fields": "status_code,status"})
        status = resp.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Media processing failed: {resp.get('status')}")
        time.sleep(5)
    raise TimeoutError(f"Media {creation_id} did not finish within {timeout_s}s")


def publish_container(creation_id: str) -> dict[str, Any]:
    return _post(f"/{_ig_user_id()}/media_publish", {"creation_id": creation_id})


def get_permalink(media_id: str) -> str | None:
    try:
        return _get(f"/{media_id}", {"fields": "permalink"}).get("permalink")
    except Exception:
        return None


# ---------- Insights / listing ----------

def list_recent_media(limit: int = 25) -> list[dict[str, Any]]:
    resp = _get(
        f"/{_ig_user_id()}/media",
        {
            "fields": "id,caption,media_type,timestamp,permalink,comments_count",
            "limit": limit,
        },
    )
    return resp.get("data", [])


# ---------- Comments ----------

def list_comments(media_id: str) -> list[dict[str, Any]]:
    resp = _get(
        f"/{media_id}/comments",
        {"fields": "id,text,username,timestamp,from,replies{id,text,username}"},
    )
    return resp.get("data", [])


def reply_to_comment(comment_id: str, message: str) -> dict[str, Any]:
    return _post(f"/{comment_id}/replies", {"message": message})


# ---------- Direct Messages (Messenger Platform) ----------

def list_conversations(limit: int = 20) -> list[dict[str, Any]]:
    resp = _get(
        f"/{_ig_user_id()}/conversations",
        {"platform": "instagram", "fields": "participants,updated_time", "limit": limit},
    )
    return resp.get("data", [])


def list_messages(conversation_id: str) -> list[dict[str, Any]]:
    resp = _get(
        f"/{conversation_id}",
        {"fields": "messages{id,from,to,message,created_time}"},
    )
    msgs = resp.get("messages", {}).get("data", [])
    return msgs


def send_message(recipient_id: str, text: str) -> dict[str, Any]:
    """Send a DM via Messenger Send API (works for IG conversations that
    messaged you within the past 24h, per Meta policy)."""
    return _post(
        f"/{_ig_user_id()}/messages",
        {
            "recipient": f'{{"id":"{recipient_id}"}}',
            "message": f'{{"text":{text!r}}}',
        },
    )
