"""YouTube Data API v3 upload (Shorts).

OAuth 2.0 desktop-app flow. Secrets live in env:
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
See README for the one-time setup walkthrough.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import env, load_config
from .models import Script, UploadResult

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _credentials() -> Credentials:
    e = env()
    missing = [k for k, v in {
        "YT_CLIENT_ID": e.yt_client_id,
        "YT_CLIENT_SECRET": e.yt_client_secret,
        "YT_REFRESH_TOKEN": e.yt_refresh_token,
    }.items() if not v]
    if missing:
        raise RuntimeError(
            f"YouTube OAuth not configured. Missing: {missing}. See README 'YouTube setup'."
        )
    creds = Credentials(
        token=None,
        refresh_token=e.yt_refresh_token,
        client_id=e.yt_client_id,
        client_secret=e.yt_client_secret,
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def _service() -> Any:
    return build("youtube", "v3", credentials=_credentials(), cache_discovery=False)


def _title_for_shorts(title: str) -> str:
    """YT treats <=60s + 9:16 + #Shorts in title/desc as a Short. Force the hashtag."""
    if "#shorts" in title.lower():
        return title[:100]
    # Append, trim to 100 chars
    candidate = f"{title} #Shorts"
    if len(candidate) <= 100:
        return candidate
    return (title[: 100 - len(" #Shorts")] + " #Shorts").strip()


def upload_short(video_path: Path, script: Script) -> UploadResult:
    cfg = load_config().upload
    title = _title_for_shorts(f"{cfg.title_prefix}{script.youtube_title}".strip())
    description = f"{script.youtube_description}\n\n#Shorts"
    tags = list(dict.fromkeys(cfg.default_tags + script.tags))[:30]

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": cfg.category_id,
        },
        "status": {
            "privacyStatus": cfg.privacy_status,
            "madeForKids": cfg.made_for_kids,
            "selfDeclaredMadeForKids": cfg.made_for_kids,
        },
    }
    svc = _service()
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    req = svc.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = req.next_chunk()
    vid = response["id"]
    return UploadResult(
        video_id=vid,
        url=f"https://youtube.com/shorts/{vid}",
        raw=response,
    )
