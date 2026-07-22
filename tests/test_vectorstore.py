"""
Minimal tests for the VectorStoreService.

Tests use a temporary LanceDB directory and mocked embedding service.
"""

from unittest.mock import MagicMock
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared mock objects
# ---------------------------------------------------------------------------

_mock_embedding = MagicMock()
_mock_embedding.model = "test-model"
_mock_embedding.embed_text.return_value = [0.0] * 1024
_mock_embedding.embed_batch.side_effect = lambda texts: [[0.0] * 1024 for _ in texts]
_mock_embedding.get_cache_stats.return_value = {
    "model": "test-model",
    "cache_size": 0,
    "hits": 0,
    "misses": 0,
}


@pytest.fixture(autouse=True)
def _patch_embedding(monkeypatch):
    monkeypatch.setattr(
        "app.services.embeddings.get_embedding_service",
        lambda: _mock_embedding,
    )


@pytest.fixture()
def vectorstore(tmp_path, _patch_embedding):
    """Create a VectorStoreService backed by a temp directory."""
    from app.services.vectorstore import VectorStoreService

    return VectorStoreService(
        db_path=tmp_path / "test_lancedb",
        embedding_service=_mock_embedding,
    )


# ===========================================================================
# Test: Initialization
# ===========================================================================


def test_vectorstore_initializes(vectorstore):
    """VectorStoreService should initialize without errors."""
    assert vectorstore is not None
    assert vectorstore.db_path.exists()


# ===========================================================================
# Test: get_stats
# ===========================================================================


def test_get_stats_returns_dict(vectorstore):
    """get_stats() should return a dict with expected keys."""
    stats = vectorstore.get_stats()
    assert "chunks_count" in stats
    assert "semantic_cache_count" in stats
    assert "retrieval_cache_size" in stats
    assert "embedding_model" in stats
    assert stats["chunks_count"] == 0
    assert stats["semantic_cache_count"] == 0


# ===========================================================================
# Test: add_chunks
# ===========================================================================


def test_add_chunks_empty_list(vectorstore):
    """add_chunks([]) should return 0 without error."""
    count = vectorstore.add_chunks([])
    assert count == 0


def test_add_chunks_single(vectorstore):
    """add_chunks with one chunk should return 1."""
    chunks = [
        {
            "paper_id": "test-paper",
            "chunk_index": 0,
            "text": "This is a test chunk about transformers.",
            "section": "body",
        }
    ]
    count = vectorstore.add_chunks(chunks)
    assert count == 1

    stats = vectorstore.get_stats()
    assert stats["chunks_count"] == 1


def test_add_chunks_multiple(vectorstore):
    """add_chunks with multiple chunks should return correct count."""
    chunks = [
        {
            "paper_id": "test-paper",
            "chunk_index": i,
            "text": f"Chunk {i} about attention mechanisms.",
        }
        for i in range(5)
    ]
    count = vectorstore.add_chunks(chunks)
    assert count == 5


# ===========================================================================
# Test: search (with mocked embeddings)
# ===========================================================================


def test_search_empty_store(vectorstore):
    """search() on empty store should return empty list."""
    results = vectorstore.search("test query", top_k=5)
    assert isinstance(results, list)
    assert len(results) == 0


def test_search_after_adding_chunks(vectorstore):
    """search() should find chunks after adding them."""
    chunks = [
        {
            "paper_id": "paper-1",
            "chunk_index": 0,
            "text": "Deep learning for image classification.",
            "title": "DL Paper",
            "year": 2023,
        }
    ]
    vectorstore.add_chunks(chunks)

    results = vectorstore.search("deep learning", top_k=5)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0]["paper_id"] == "paper-1"


# ===========================================================================
# Test: delete_paper
# ===========================================================================


def test_delete_paper(vectorstore):
    """delete_paper should remove chunks for that paper_id."""
    chunks = [
        {
            "paper_id": "to-delete",
            "chunk_index": 0,
            "text": "This will be deleted.",
        }
    ]
    vectorstore.add_chunks(chunks)
    assert vectorstore.get_stats()["chunks_count"] == 1

    vectorstore.delete_paper("to-delete")
    assert vectorstore.get_stats()["chunks_count"] == 0


# ===========================================================================
# Test: semantic cache
# ===========================================================================


def test_search_semantic_cache_empty(vectorstore):
    """search_semantic_cache on empty cache should return None."""
    result = vectorstore.search_semantic_cache("some query")
    assert result is None
