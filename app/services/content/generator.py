"""Generador de contenido para posts de Instagram desde un paper."""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import get_settings
from app.models.instagram import GeneratedContent
from app.services.vectorstore import get_vectorstore_service

log = logging.getLogger(__name__)


def _load_system_prompt() -> str:
    here = Path(__file__).resolve().parents[3]
    path = here / "prompts" / "instagram_post.md"
    return path.read_text(encoding="utf-8")


def _build_user_prompt(
    title: str,
    authors: list[str],
    year: Optional[int],
    abstract: str,
    chunks: list[str],
    extra_instructions: Optional[str] = None,
) -> str:
    chunks_block = "\n\n---\n\n".join(c.strip() for c in chunks if c)
    parts = [
        f"Paper title: {title}",
        f"Authors: {', '.join(authors) if authors else 'Unknown'}",
        f"Year: {year if year else 'Unknown'}",
        "",
        "Abstract:",
        abstract or "(no abstract available)",
        "",
        "Selected excerpts from the paper:",
        chunks_block or "(no excerpts available)",
    ]
    if extra_instructions:
        parts.extend(["", "Editorial instructions:", extra_instructions])
    return "\n".join(parts)


def _coerce_json(raw: str) -> dict:
    """LLMs aveces devuelven texto extra; rescatamos el primer objeto JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE)
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM output: {raw[:200]}")
    return json.loads(match.group(0))


class ContentGenerator:
    """Genera caption + image_prompt llamando a Ollama directo."""

    def __init__(
        self,
        ollama_base_url: str,
        llm_model: str,
        max_chunks: int = 8,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = ollama_base_url.rstrip("/")
        self.model = llm_model
        self.max_chunks = max_chunks
        self.timeout = timeout
        self._system_prompt = _load_system_prompt()
        self._vectorstore = get_vectorstore_service()

    def gather_paper_context(
        self,
        paper_id: str,
        max_chunks: Optional[int] = None,
    ) -> tuple[dict, list[str]]:
        """Devuelve (metadata_dict, lista_de_textos_de_chunks)."""
        chunks = self._vectorstore.get_chunks_by_paper(
            paper_id, limit=max_chunks or self.max_chunks
        )
        if not chunks:
            return {}, []

        first = chunks[0]
        meta = {
            "title": first.get("title") or first.get("paper_title") or paper_id,
            "authors": first.get("authors") or [],
            "year": first.get("year"),
            "abstract": first.get("abstract") or "",
            "url": first.get("url") or first.get("source_url"),
        }
        if isinstance(meta["authors"], str):
            meta["authors"] = [
                a.strip() for a in meta["authors"].split(",") if a.strip()
            ]
        texts = [c.get("text") or c.get("content") or "" for c in chunks]
        return meta, [t for t in texts if t]

    async def generate(
        self,
        paper_meta: dict,
        chunks: list[str],
        extra_instructions: Optional[str] = None,
    ) -> GeneratedContent:
        user_prompt = _build_user_prompt(
            title=paper_meta.get("title", "Untitled"),
            authors=paper_meta.get("authors", []) or [],
            year=paper_meta.get("year"),
            abstract=paper_meta.get("abstract", "") or "",
            chunks=chunks[: self.max_chunks],
            extra_instructions=extra_instructions,
        )

        body = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.55, "num_ctx": 8192},
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()

        raw = data.get("message", {}).get("content", "")
        parsed = _coerce_json(raw)

        # Normalize hashtags: lowercase, no '#', no spaces.
        tags = parsed.get("hashtags") or []
        if isinstance(tags, str):
            tags = re.findall(r"#?(\w+)", tags)
        tags = [
            re.sub(r"\W+", "", t).lower()
            for t in tags
            if isinstance(t, str) and t.strip()
        ]

        return GeneratedContent(
            hook=str(parsed.get("hook", "")).strip()[:120],
            caption=str(parsed.get("caption", "")).strip()[:2200],
            hashtags=tags[:30],
            alt_text=str(parsed.get("alt_text", "")).strip()[:200],
            image_prompt=str(parsed.get("image_prompt", "")).strip()[:500],
            image_negative_prompt=str(
                parsed.get("image_negative_prompt", "")
            ).strip()[:300],
        )


@lru_cache
def get_content_generator() -> ContentGenerator:
    settings = get_settings()
    return ContentGenerator(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", settings.ollama_base_url),
        llm_model=os.getenv("LLM_MODEL", settings.llm_model),
    )
