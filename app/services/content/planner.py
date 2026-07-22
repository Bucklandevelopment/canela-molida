"""Selecciona qué paper convertir en post (local o por descubrimiento)."""

from __future__ import annotations

import json
import logging
import random
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.models.instagram import PostSource
from app.services.apis.arxiv import ArxivClient
from app.services.content.store import get_post_store
from app.services.vectorstore import get_vectorstore_service

log = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [
    "cs.AI",
    "cs.CL",
    "cs.LG",
    "math.CO",
    "physics.gen-ph",
    "physics.bio-ph",
    "q-bio.NC",
    "stat.ML",
]


def _load_taxonomy() -> list[str]:
    here = Path(__file__).resolve().parents[3]
    path = here / "taxonomy" / "arxiv_categories.json"
    if not path.exists():
        return DEFAULT_CATEGORIES
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cats: list[str] = []
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    cats.extend(v)
                elif isinstance(v, dict):
                    cats.extend(v.keys())
        elif isinstance(data, list):
            cats = [str(x) for x in data]
        return cats or DEFAULT_CATEGORIES
    except Exception:
        return DEFAULT_CATEGORIES


class ContentPlanner:
    """Decide el siguiente paper a procesar."""

    def __init__(self) -> None:
        self._vectorstore = get_vectorstore_service()
        self._store = get_post_store()
        self._categories = _load_taxonomy()

    async def pick_local(self) -> Optional[dict]:
        """Devuelve metadata de un paper indexado que aún no tenga draft."""
        paper_ids = self._vectorstore.list_paper_ids(limit=500)
        if not paper_ids:
            return None
        random.shuffle(paper_ids)
        for pid in paper_ids:
            if not await self._store.has_paper(pid):
                chunks = self._vectorstore.get_chunks_by_paper(pid, limit=1)
                if not chunks:
                    continue
                first = chunks[0]
                return {
                    "paper_id": pid,
                    "title": first.get("title") or pid,
                    "authors": first.get("authors") or [],
                    "year": first.get("year"),
                    "url": first.get("url"),
                    "source": PostSource.LOCAL,
                }
        return None

    async def discover_arxiv(
        self,
        category: Optional[str] = None,
        max_candidates: int = 10,
    ) -> Optional[dict]:
        """Sugiere un paper reciente de arXiv (no lo ingesta)."""
        cat = category or random.choice(self._categories)
        client = ArxivClient()
        try:
            entries = await client.search_by_category(cat, max_results=max_candidates)
        except Exception as exc:
            log.warning("arXiv discovery failed for %s: %s", cat, exc)
            return None
        finally:
            await client.close()

        for entry in entries:
            arxiv_id = getattr(entry, "arxiv_id", None) or getattr(entry, "id", None)
            if not arxiv_id:
                continue
            paper_id = f"arxiv:{arxiv_id}"
            if await self._store.has_paper(paper_id):
                continue
            return {
                "paper_id": paper_id,
                "arxiv_id": arxiv_id,
                "title": getattr(entry, "title", arxiv_id),
                "authors": [
                    getattr(a, "name", str(a))
                    for a in (getattr(entry, "authors", []) or [])
                ],
                "year": getattr(
                    getattr(entry, "published", None), "year", None
                ),
                "abstract": getattr(entry, "summary", "")
                or getattr(entry, "abstract", ""),
                "url": getattr(entry, "pdf_url", None)
                or getattr(entry, "url", None),
                "source": PostSource.ARXIV,
            }
        return None

    async def pick(
        self,
        source: PostSource = PostSource.LOCAL,
        category: Optional[str] = None,
    ) -> Optional[dict]:
        if source == PostSource.LOCAL:
            picked = await self.pick_local()
            if picked:
                return picked
            return await self.discover_arxiv(category=category)
        if source == PostSource.ARXIV:
            return await self.discover_arxiv(category=category)
        return await self.pick_local()


@lru_cache
def get_content_planner() -> ContentPlanner:
    return ContentPlanner()
