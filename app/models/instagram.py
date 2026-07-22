"""Pydantic models for Instagram automation."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class PostStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FAILED = "failed"


class PostSource(str, Enum):
    LOCAL = "local"
    ARXIV = "arxiv"
    OPENALEX = "openalex"


class GeneratedContent(BaseModel):
    hook: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    alt_text: str = ""
    image_prompt: str = ""
    image_negative_prompt: str = ""


class PostDraft(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    paper_id: str
    paper_title: str
    paper_authors: list[str] = Field(default_factory=list)
    paper_year: Optional[int] = None
    paper_url: Optional[str] = None

    source: PostSource = PostSource.LOCAL
    status: PostStatus = PostStatus.DRAFT

    content: GeneratedContent
    image_path: Optional[str] = None

    ig_media_id: Optional[str] = None
    ig_permalink: Optional[str] = None
    error: Optional[str] = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    published_at: Optional[datetime] = None


class GenerateRequest(BaseModel):
    paper_id: Optional[str] = None
    arxiv_id: Optional[str] = None
    source: PostSource = PostSource.LOCAL
    category: Optional[str] = None
    instructions: Optional[str] = None


class ApprovalRequest(BaseModel):
    publish_now: bool = False


class RegenerateRequest(BaseModel):
    regenerate_caption: bool = True
    regenerate_image: bool = False
    instructions: Optional[str] = None
