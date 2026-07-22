"""APScheduler que dispara la generación de drafts a intervalos."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Optional

from app.models.instagram import PostDraft, PostSource, PostStatus
from app.services.content.generator import get_content_generator
from app.services.content.planner import get_content_planner
from app.services.content.renderer import get_image_renderer
from app.services.content.store import get_post_store

log = logging.getLogger(__name__)


async def generate_draft_for(
    paper: dict,
    extra_instructions: Optional[str] = None,
    skip_image: bool = False,
) -> PostDraft:
    """Núcleo del pipeline: paper → caption + imagen → draft persistido."""
    generator = get_content_generator()
    renderer = get_image_renderer()
    store = get_post_store()

    paper_id = paper["paper_id"]
    meta, chunks = generator.gather_paper_context(paper_id)
    if not meta:
        meta = {
            "title": paper.get("title", paper_id),
            "authors": paper.get("authors") or [],
            "year": paper.get("year"),
            "abstract": paper.get("abstract", ""),
            "url": paper.get("url"),
        }

    content = await generator.generate(meta, chunks, extra_instructions)

    image_path = None
    if not skip_image and content.image_prompt:
        try:
            image_path = await renderer.generate(
                prompt=content.image_prompt,
                negative_prompt=content.image_negative_prompt,
            )
        except Exception as exc:
            log.warning("Image generation failed for %s: %s", paper_id, exc)

    draft = PostDraft(
        paper_id=paper_id,
        paper_title=meta.get("title") or paper_id,
        paper_authors=meta.get("authors") or [],
        paper_year=meta.get("year"),
        paper_url=meta.get("url"),
        source=PostSource(paper.get("source", PostSource.LOCAL)),
        status=PostStatus.DRAFT,
        content=content,
        image_path=str(image_path) if image_path else None,
    )
    return await store.save(draft)


async def generate_scheduled_draft() -> Optional[PostDraft]:
    """Job periódico: elige paper y genera draft. None si no hay candidato."""
    planner = get_content_planner()
    paper = await planner.pick(source=PostSource.LOCAL)
    if not paper:
        log.info("Scheduler: no candidate paper available")
        return None
    log.info("Scheduler: generating draft for %s", paper["paper_id"])
    try:
        return await generate_draft_for(paper)
    except Exception as exc:
        log.exception("Scheduler: draft generation failed: %s", exc)
        return None


class ContentScheduler:
    """Wrapper alrededor de APScheduler para integrarse al lifespan FastAPI."""

    def __init__(self, interval_minutes: int = 360, enabled: bool = False) -> None:
        self.interval_minutes = max(15, interval_minutes)
        self.enabled = enabled
        self._scheduler: Optional[Any] = None

    def start(self) -> None:
        if not self.enabled:
            log.info("ContentScheduler disabled (CONTENT_SCHEDULER_ENABLED=false)")
            return
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError:
            log.warning("APScheduler not installed; scheduler not started")
            return
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            generate_scheduled_draft,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id="generate_instagram_draft",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        self._scheduler = scheduler
        log.info(
            "ContentScheduler started (every %d min)", self.interval_minutes
        )

    def shutdown(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            log.info("ContentScheduler stopped")


@lru_cache
def get_scheduler() -> ContentScheduler:
    interval = int(os.getenv("CONTENT_SCHEDULER_INTERVAL_MIN", "360"))
    enabled = os.getenv("CONTENT_SCHEDULER_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    return ContentScheduler(interval_minutes=interval, enabled=enabled)
