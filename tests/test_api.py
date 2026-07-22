"""
Minimal API tests for Scientific Library RAG.

Tests use mocked services so they run without Ollama, LanceDB, or GROBID.
"""

from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from httpx import AsyncClient, ASGITransport

# Patch heavy services before importing app
_mock_embedding = MagicMock()
_mock_embedding.model = "test-model"
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


@pytest.fixture()
async def client(_patch_services):
    """Create an async test client for the FastAPI app."""
    # Import app after patching
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===========================================================================
# Test: Root endpoint
# ===========================================================================


@pytest.mark.asyncio
async def test_root(client):
    """GET / should return API metadata."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Scientific Library RAG"
    assert "version" in data
    assert data["docs"] == "/docs"


# ===========================================================================
# Test: Health endpoint
# ===========================================================================


@pytest.mark.asyncio
async def test_health(client):
    """GET /health should return healthy status with service info."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "embedding_model" in data
    assert "embedding_cache" in data
    assert "vectorstore" in data


# ===========================================================================
# Test: Stats endpoint
# ===========================================================================


@pytest.mark.asyncio
async def test_stats(client):
    """GET /stats should return vectorstore and embedding stats."""
    response = await client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "vectorstore" in data
    assert "embeddings" in data


# ===========================================================================
# Test: Search papers endpoint
# ===========================================================================


@pytest.mark.asyncio
async def test_search_papers_returns_results(client):
    """GET /search/papers should return search results structure."""
    response = await client.get("/search/papers", params={"query": "test"})
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert data["query"] == "test"
    assert "count" in data
    assert "results" in data
    assert isinstance(data["results"], list)


# ===========================================================================
# Test: Ingest PDF endpoint (mock)
# ===========================================================================


@pytest.mark.asyncio
async def test_ingest_pdf_requires_file(client):
    """POST /ingest/pdf without file should return 422."""
    response = await client.post("/ingest/pdf")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_pdf_with_mock(client, monkeypatch):
    """POST /ingest/pdf with a mock PDF should succeed."""
    mock_processor = MagicMock()
    mock_processor.process_pdf = AsyncMock(return_value={
        "text": "Test content",
        "chunks": [{"text": "chunk1", "paper_id": "test"}],
        "metadata": None,
        "grobid_used": False,
    })
    monkeypatch.setattr(
        "app.api.ingest.get_pdf_processor",
        lambda: mock_processor,
    )

    pdf_content = b"%PDF-1.4 fake pdf content"
    response = await client.post(
        "/ingest/pdf",
        files={"file": ("test.pdf", pdf_content, "application/pdf")},
        data={"use_grobid": "false"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["paper_id"] == "test"
    assert data["chunks_count"] == 1


# ===========================================================================
# Test: CORS headers
# ===========================================================================


@pytest.mark.asyncio
async def test_cors_allowed_origin(client):
    """Requests from allowed origin should get CORS headers."""
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_cors_disallowed_origin(client):
    """Requests from disallowed origin should not get CORS allow header."""
    response = await client.get(
        "/health",
        headers={"Origin": "http://evil.example.com"},
    )
    # FastAPI CORS middleware does not set allow-origin for disallowed origins
    cors_header = response.headers.get("access-control-allow-origin", "")
    assert "evil.example.com" not in cors_header
