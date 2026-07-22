"""FastAPI router para gestión de drafts y publicación a Instagram."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from app.models.instagram import (
    ApprovalRequest,
    GenerateRequest,
    PostDraft,
    PostStatus,
    RegenerateRequest,
)
from app.services.content.generator import get_content_generator
from app.services.content.planner import get_content_planner
from app.services.content.publisher import get_publisher
from app.services.content.renderer import get_image_renderer
from app.services.content.scheduler import generate_draft_for
from app.services.content.store import get_post_store

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/instagram", tags=["Instagram"])


@router.post("/drafts", response_model=PostDraft)
async def create_draft(req: GenerateRequest) -> PostDraft:
    """Genera un nuevo draft, opcionalmente para un paper concreto."""
    planner = get_content_planner()

    if req.paper_id:
        paper = {
            "paper_id": req.paper_id,
            "title": req.paper_id,
            "authors": [],
            "year": None,
            "url": None,
            "source": req.source,
        }
    elif req.arxiv_id:
        paper = {
            "paper_id": f"arxiv:{req.arxiv_id}",
            "arxiv_id": req.arxiv_id,
            "source": req.source,
        }
    else:
        paper = await planner.pick(source=req.source, category=req.category)
        if not paper:
            raise HTTPException(404, "No candidate paper found")

    try:
        return await generate_draft_for(paper, extra_instructions=req.instructions)
    except Exception as exc:
        log.exception("Draft generation failed")
        raise HTTPException(500, f"Draft generation failed: {exc}") from exc


@router.get("/drafts", response_model=list[PostDraft])
async def list_drafts(
    status: PostStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[PostDraft]:
    store = get_post_store()
    return await store.list(status=status, limit=limit)


@router.get("/drafts/{draft_id}", response_model=PostDraft)
async def get_draft(draft_id: str) -> PostDraft:
    store = get_post_store()
    draft = await store.get(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    return draft


@router.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str) -> dict:
    store = get_post_store()
    if not await store.delete(draft_id):
        raise HTTPException(404, "Draft not found")
    return {"deleted": draft_id}


@router.post("/drafts/{draft_id}/regenerate", response_model=PostDraft)
async def regenerate_draft(
    draft_id: str,
    req: RegenerateRequest,
) -> PostDraft:
    store = get_post_store()
    draft = await store.get(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status == PostStatus.PUBLISHED:
        raise HTTPException(409, "Cannot regenerate a published post")

    if req.regenerate_caption:
        generator = get_content_generator()
        meta, chunks = generator.gather_paper_context(draft.paper_id)
        if not meta:
            meta = {
                "title": draft.paper_title,
                "authors": draft.paper_authors,
                "year": draft.paper_year,
                "abstract": "",
                "url": draft.paper_url,
            }
        draft.content = await generator.generate(meta, chunks, req.instructions)

    if req.regenerate_image and draft.content.image_prompt:
        renderer = get_image_renderer()
        try:
            new_path = await renderer.generate(
                prompt=draft.content.image_prompt,
                negative_prompt=draft.content.image_negative_prompt,
            )
            draft.image_path = str(new_path)
        except Exception as exc:
            log.warning("Image regeneration failed for %s: %s", draft_id, exc)

    draft.status = PostStatus.DRAFT
    draft.error = None
    return await store.save(draft)


@router.post("/drafts/{draft_id}/approve", response_model=PostDraft)
async def approve_draft(
    draft_id: str,
    req: ApprovalRequest,
    background: BackgroundTasks,
) -> PostDraft:
    store = get_post_store()
    draft = await store.get(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status == PostStatus.PUBLISHED:
        raise HTTPException(409, "Already published")

    draft.status = PostStatus.APPROVED
    await store.save(draft)

    if req.publish_now:
        background.add_task(_publish_in_background, draft_id)

    return draft


@router.post("/drafts/{draft_id}/reject", response_model=PostDraft)
async def reject_draft(draft_id: str) -> PostDraft:
    store = get_post_store()
    draft = await store.get(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    draft.status = PostStatus.REJECTED
    return await store.save(draft)


@router.post("/drafts/{draft_id}/publish", response_model=PostDraft)
async def publish_draft(draft_id: str) -> PostDraft:
    return await _publish_in_background(draft_id)


@router.get("/images/{filename}")
async def get_image(filename: str) -> FileResponse:
    """Sirve la imagen del draft para preview en el frontend
    y también para que la Graph API la descargue al publicar."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    from app.core.config import get_settings

    img_dir = Path(get_settings().data_dir) / "instagram" / "images"
    path = img_dir / filename
    if not path.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(path, media_type="image/png")


async def _publish_in_background(draft_id: str) -> PostDraft:
    store = get_post_store()
    draft = await store.get(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    if not draft.image_path:
        raise HTTPException(400, "Draft has no image")

    publisher = get_publisher()
    if not publisher.configured:
        draft.status = PostStatus.FAILED
        draft.error = "Publisher not configured (missing IG_* env vars)"
        await store.save(draft)
        raise HTTPException(503, draft.error)

    caption = _compose_full_caption(draft)
    try:
        result = await publisher.publish(Path(draft.image_path), caption)
    except Exception as exc:
        draft.status = PostStatus.FAILED
        draft.error = str(exc)
        await store.save(draft)
        raise HTTPException(500, f"Publish failed: {exc}") from exc

    draft.status = PostStatus.PUBLISHED
    draft.ig_media_id = result.get("media_id")
    draft.ig_permalink = result.get("permalink")
    draft.published_at = datetime.now(timezone.utc)
    draft.error = None
    return await store.save(draft)


def _compose_full_caption(draft: PostDraft) -> str:
    body = draft.content.caption.strip()
    tags = " ".join(f"#{t}" for t in draft.content.hashtags if t)
    if tags and tags not in body:
        body = f"{body}\n\n{tags}"
    return body[:2200]
