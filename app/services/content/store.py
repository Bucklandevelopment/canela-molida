"""Persistencia de drafts/posts en SQLite (aiosqlite)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import aiosqlite

from app.core.config import get_settings
from app.models.instagram import GeneratedContent, PostDraft, PostSource, PostStatus

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    paper_title TEXT NOT NULL,
    paper_authors TEXT NOT NULL,
    paper_year INTEGER,
    paper_url TEXT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    content_json TEXT NOT NULL,
    image_path TEXT,
    ig_media_id TEXT,
    ig_permalink TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    published_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_paper ON posts(paper_id);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);
"""


def _row_to_draft(row: aiosqlite.Row) -> PostDraft:
    from datetime import datetime

    def _dt(value: Optional[str]):
        return datetime.fromisoformat(value) if value else None

    return PostDraft(
        id=row["id"],
        paper_id=row["paper_id"],
        paper_title=row["paper_title"],
        paper_authors=json.loads(row["paper_authors"] or "[]"),
        paper_year=row["paper_year"],
        paper_url=row["paper_url"],
        source=PostSource(row["source"]),
        status=PostStatus(row["status"]),
        content=GeneratedContent(**json.loads(row["content_json"])),
        image_path=row["image_path"],
        ig_media_id=row["ig_media_id"],
        ig_permalink=row["ig_permalink"],
        error=row["error"],
        created_at=_dt(row["created_at"]),  # type: ignore[arg-type]
        updated_at=_dt(row["updated_at"]),  # type: ignore[arg-type]
        published_at=_dt(row["published_at"]),
    )


class PostStore:
    """Repositorio async de drafts en SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _connect(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        if not self._initialized:
            await conn.executescript(_SCHEMA)
            await conn.commit()
            self._initialized = True
        return conn

    async def save(self, draft: PostDraft) -> PostDraft:
        from datetime import datetime, timezone

        draft.updated_at = datetime.now(timezone.utc)
        async with await self._connect() as conn:
            await conn.execute(
                """
                INSERT INTO posts
                  (id, paper_id, paper_title, paper_authors, paper_year, paper_url,
                   source, status, content_json, image_path, ig_media_id,
                   ig_permalink, error, created_at, updated_at, published_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  paper_title=excluded.paper_title,
                  paper_authors=excluded.paper_authors,
                  paper_year=excluded.paper_year,
                  paper_url=excluded.paper_url,
                  source=excluded.source,
                  status=excluded.status,
                  content_json=excluded.content_json,
                  image_path=excluded.image_path,
                  ig_media_id=excluded.ig_media_id,
                  ig_permalink=excluded.ig_permalink,
                  error=excluded.error,
                  updated_at=excluded.updated_at,
                  published_at=excluded.published_at
                """,
                (
                    draft.id,
                    draft.paper_id,
                    draft.paper_title,
                    json.dumps(draft.paper_authors),
                    draft.paper_year,
                    draft.paper_url,
                    draft.source.value,
                    draft.status.value,
                    draft.content.model_dump_json(),
                    draft.image_path,
                    draft.ig_media_id,
                    draft.ig_permalink,
                    draft.error,
                    draft.created_at.isoformat(),
                    draft.updated_at.isoformat(),
                    draft.published_at.isoformat() if draft.published_at else None,
                ),
            )
            await conn.commit()
        return draft

    async def get(self, draft_id: str) -> Optional[PostDraft]:
        async with await self._connect() as conn:
            cur = await conn.execute("SELECT * FROM posts WHERE id = ?", (draft_id,))
            row = await cur.fetchone()
            return _row_to_draft(row) if row else None

    async def list(
        self,
        status: Optional[PostStatus] = None,
        limit: int = 50,
    ) -> list[PostDraft]:
        async with await self._connect() as conn:
            if status is not None:
                cur = await conn.execute(
                    "SELECT * FROM posts WHERE status = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (status.value, limit),
                )
            else:
                cur = await conn.execute(
                    "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            rows = await cur.fetchall()
            return [_row_to_draft(r) for r in rows]

    async def delete(self, draft_id: str) -> bool:
        async with await self._connect() as conn:
            cur = await conn.execute("DELETE FROM posts WHERE id = ?", (draft_id,))
            await conn.commit()
            return cur.rowcount > 0

    async def has_paper(self, paper_id: str) -> bool:
        async with await self._connect() as conn:
            cur = await conn.execute(
                "SELECT 1 FROM posts WHERE paper_id = ? LIMIT 1", (paper_id,)
            )
            return await cur.fetchone() is not None


@lru_cache
def get_post_store() -> PostStore:
    settings = get_settings()
    db_path = Path(settings.data_dir) / "instagram" / "posts.sqlite"
    return PostStore(db_path)
