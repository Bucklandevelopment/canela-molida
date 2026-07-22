"""
Minimal tests for the RAG service and API router.

Tests use mocked services so they run without Ollama, LanceDB, or GROBID.
"""

from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Shared mock objects
# ---------------------------------------------------------------------------

_mock_embedding = MagicMock()
_mock_embedding.model = "test-model"
_mock_embedding.embed_text.return_value = [0.0] * 1024
_mock_embedding.embed_batch.return_value = [[0.0] * 1024]
_mock_embedding.get_cache_stats.return_value = {
    "model": "test-model",
    "cache_size": 0,
    "hits": 0,
    "misses": 0,
}

_mock_vectorstore = MagicMock()
_mock_vectorstore.get_stats.return_value = {
    "chunks_count": 0,
    "semantic_cache_count": 0,
    "retrieval_cache_size": 0,
}
_mock_vectorstore.search.return_value = []
_mock_vectorstore.add_chunks.return_value = 0
_mock_vectorstore.search_semantic_cache.return_value = None


@pytest.fixture(autouse=True)
def _patch_services(monkeypatch):
    """Patch all heavy services so the app starts without external deps."""
    monkeypatch.setattr(
        "app.services.embeddings.get_embedding_service",
        lambda: _mock_embedding,
    )
    monkeypatch.setattr(
        "app.services.vectorstore.get_vectorstore_service",
        lambda: _mock_vectorstore,
    )
    # Also patch the RAG service singleton so it uses our mocks
    from app.services.rag import RAGService, get_rag_service
    get_rag_service.cache_clear()
    mock_rag = RAGService(
        embedding_service=_mock_embedding,
        vectorstore_service=_mock_vectorstore,
    )
    monkeypatch.setattr(
        "app.services.rag.get_rag_service",
        lambda: mock_rag,
    )
    monkeypatch.setattr(
        "app.api.rag.get_rag_service",
        lambda: mock_rag,
    )


@pytest.fixture()
async def client(_patch_services):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===========================================================================
# Test: RAG search endpoint (vector search only, no LLM)
# ===========================================================================


@pytest.mark.asyncio
async def test_rag_search_returns_list(client):
    """GET /rag/search should return a list of results."""
    response = await client.get("/rag/search", params={"query": "attention mechanism"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_rag_search_with_year_filter(client):
    """GET /rag/search with year filters should not error."""
    response = await client.get(
        "/rag/search",
        params={"query": "transformers", "year_min": 2020, "year_max": 2024, "top_k": 5},
    )
    assert response.status_code == 200


# ===========================================================================
# Test: RAG ask endpoint (GET convenience wrapper)
# ===========================================================================


@pytest.mark.asyncio
async def test_rag_ask_requires_question(client):
    """GET /rag/ask without question should return 422."""
    response = await client.get("/rag/ask")
    assert response.status_code == 422


# ===========================================================================
# Test: RAG query endpoint (POST, requires LLM - mocked)
# ===========================================================================


@pytest.mark.asyncio
async def test_rag_query_requires_body(client):
    """POST /rag/query without body should return 422."""
    response = await client.post("/rag/query")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rag_query_validates_temperature(client):
    """POST /rag/query with invalid temperature should return 422."""
    response = await client.post(
        "/rag/query",
        json={"question": "test", "temperature": 5.0},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rag_query_validates_top_k(client):
    """POST /rag/query with top_k out of range should return 422."""
    response = await client.post(
        "/rag/query",
        json={"question": "test", "top_k": 0},
    )
    assert response.status_code == 422
