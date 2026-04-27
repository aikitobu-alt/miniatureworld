"""SQLite state: which media files have been posted, which comments/DMs replied to."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import project_root

DB_PATH = project_root() / "data" / "instagram.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS posted_media (
    file_relpath TEXT PRIMARY KEY,
    file_hash    TEXT,
    media_type   TEXT,             -- IMAGE | VIDEO | REELS | CAROUSEL
    ig_media_id  TEXT,             -- Instagram media ID
    caption      TEXT,
    posted_at    TEXT NOT NULL DEFAULT (datetime('now')),
    permalink    TEXT
);

CREATE TABLE IF NOT EXISTS replied_comments (
    comment_id   TEXT PRIMARY KEY,
    media_id     TEXT,
    reply_text   TEXT,
    replied_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS replied_messages (
    message_id   TEXT PRIMARY KEY,
    sender_id    TEXT,
    reply_text   TEXT,
    replied_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


# ---- posted_media ----

def is_posted(file_relpath: str) -> bool:
    with conn() as c:
        cur = c.execute("SELECT 1 FROM posted_media WHERE file_relpath = ?", (file_relpath,))
        return cur.fetchone() is not None


def mark_posted(
    *,
    file_relpath: str,
    file_hash: str,
    media_type: str,
    ig_media_id: str,
    caption: str,
    permalink: str | None,
) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO posted_media "
            "(file_relpath, file_hash, media_type, ig_media_id, caption, permalink) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (file_relpath, file_hash, media_type, ig_media_id, caption, permalink),
        )


def list_posted_media_ids() -> list[str]:
    """Return posted Instagram media IDs, newest first."""
    with conn() as c:
        return [r["ig_media_id"] for r in c.execute(
            "SELECT ig_media_id FROM posted_media "
            "WHERE ig_media_id IS NOT NULL "
            "ORDER BY posted_at DESC"
        )]


# ---- replies ----

def has_replied_comment(comment_id: str) -> bool:
    with conn() as c:
        return c.execute(
            "SELECT 1 FROM replied_comments WHERE comment_id = ?", (comment_id,)
        ).fetchone() is not None


def record_comment_reply(comment_id: str, media_id: str, reply_text: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO replied_comments (comment_id, media_id, reply_text) "
            "VALUES (?, ?, ?)",
            (comment_id, media_id, reply_text),
        )


def has_replied_message(message_id: str) -> bool:
    with conn() as c:
        return c.execute(
            "SELECT 1 FROM replied_messages WHERE message_id = ?", (message_id,)
        ).fetchone() is not None


def record_message_reply(message_id: str, sender_id: str, reply_text: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO replied_messages (message_id, sender_id, reply_text) "
            "VALUES (?, ?, ?)",
            (message_id, sender_id, reply_text),
        )
