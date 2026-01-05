"""Pydantic models for scientific papers and RAG system."""

from app.models.paper import (
    Paper,
    PaperMetadata,
    PaperChunk,
    Author,
    SearchResult,
    SearchQuery,
)
from app.models.rag import (
    RAGQuery,
    RAGResponse,
    RetrievedContext,
)
from app.models.api import (
    OpenAlexWork,
    ArxivEntry,
    UnpaywallResponse,
)

__all__ = [
    "Paper",
    "PaperMetadata",
    "PaperChunk",
    "Author",
    "SearchResult",
    "SearchQuery",
    "RAGQuery",
    "RAGResponse",
    "RetrievedContext",
    "OpenAlexWork",
    "ArxivEntry",
    "UnpaywallResponse",
]
