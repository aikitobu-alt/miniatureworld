"""Tiny SQLite-backed log of topics used and uploads performed.

Used to (a) avoid duplicate topics, (b) track pipeline runs, (c) power a
future analytics dashboard.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .config import project_root

DB_PATH = project_root() / "data" / "state.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    slug TEXT PRIMARY KEY,
    headline TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used_at TEXT
);
CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_slug TEXT NOT NULL,
    video_id TEXT,
    url TEXT,
    title TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    meta_json TEXT
);
"""


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def record_topic(slug: str, headline: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO topics(slug, headline, created_at) VALUES(?,?,?)",
            (slug, headline, datetime.utcnow().isoformat()),
        )


def mark_topic_used(slug: str) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE topics SET used_at=? WHERE slug=?",
            (datetime.utcnow().isoformat(), slug),
        )


def used_topic_slugs(limit: int = 500) -> list[str]:
    with _conn() as c:
        rows = c.execute(
            "SELECT slug FROM topics WHERE used_at IS NOT NULL "
            "ORDER BY used_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r[0] for r in rows]


def record_upload(
    *,
    topic_slug: str,
    video_id: str | None,
    url: str | None,
    title: str,
    status: str,
    meta: dict | None = None,
) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO uploads(topic_slug, video_id, url, title, status, "
            "created_at, meta_json) VALUES(?,?,?,?,?,?,?)",
            (
                topic_slug,
                video_id,
                url,
                title,
                status,
                datetime.utcnow().isoformat(),
                json.dumps(meta or {}),
            ),
        )
