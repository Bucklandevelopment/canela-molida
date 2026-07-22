"""
Minimal tests for the PDFProcessor service.

Tests focus on the chunking and section detection logic which run locally
without requiring GROBID or actual PDF files.
"""

from unittest.mock import MagicMock
import pytest

from app.services.pdf_processor import PDFProcessor


@pytest.fixture(autouse=True)
def _patch_embedding(monkeypatch):
    mock = MagicMock()
    mock.model = "test-model"
    mock.get_cache_stats.return_value = {"model": "test-model", "cache_size": 0, "hits": 0, "misses": 0}
    monkeypatch.setattr(
        "app.services.embeddings.get_embedding_service",
        lambda: mock,
    )


@pytest.fixture()
def processor():
    """Create a PDFProcessor with default settings."""
    return PDFProcessor(chunk_size=100, chunk_overlap=20)


# ===========================================================================
# Test: create_chunks
# ===========================================================================


def test_create_chunks_returns_list(processor):
    """create_chunks should return a list of dicts."""
    text = "Hello world. " * 20
    chunks = processor.create_chunks(text, paper_id="test-paper")
    assert isinstance(chunks, list)
    assert len(chunks) > 0


def test_create_chunks_sets_paper_id(processor):
    """Each chunk should have the correct paper_id."""
    chunks = processor.create_chunks("Some text content.", paper_id="my-paper")
    for chunk in chunks:
        assert chunk["paper_id"] == "my-paper"


def test_create_chunks_sequential_indices(processor):
    """Chunk indices should be sequential starting from 0."""
    text = "A paragraph of text. " * 50
    chunks = processor.create_chunks(text, paper_id="p1")
    indices = [c["chunk_index"] for c in chunks]
    assert indices == list(range(len(chunks)))


def test_create_chunks_with_metadata(processor):
    """Metadata dict should be merged into each chunk."""
    text = "Test content for chunking."
    metadata = {"title": "My Paper", "year": 2024, "authors": ["Alice"]}
    chunks = processor.create_chunks(text, paper_id="p1", metadata=metadata)
    for chunk in chunks:
        assert chunk["title"] == "My Paper"
        assert chunk["year"] == 2024


def test_create_chunks_empty_text(processor):
    """Empty text should return empty list."""
    chunks = processor.create_chunks("", paper_id="empty")
    assert chunks == []


# ===========================================================================
# Test: _detect_section
# ===========================================================================


def test_detect_section_abstract(processor):
    assert processor._detect_section("# Abstract\nThis paper presents...") == "abstract"


def test_detect_section_introduction(processor):
    assert processor._detect_section("## Introduction\nIn recent years...") == "introduction"


def test_detect_section_methods(processor):
    assert processor._detect_section("## Methods\nWe used a dataset...") == "methods"


def test_detect_section_results(processor):
    assert processor._detect_section("Results\nOur experiments show...") == "results"


def test_detect_section_conclusion(processor):
    assert processor._detect_section("# Conclusion\nIn this work...") == "conclusion"


def test_detect_section_references(processor):
    assert processor._detect_section("References\n[1] Smith et al.") == "references"


def test_detect_section_body_fallback(processor):
    """Unknown text should return 'body'."""
    assert processor._detect_section("Some random text without a header.") == "body"


# ===========================================================================
# Test: _recursive_split
# ===========================================================================


def test_recursive_split_short_text(processor):
    """Text shorter than chunk_size should return as-is."""
    result = processor._recursive_split("Short text", ["\n\n", "\n", ". "], 100)
    assert result == ["Short text"]


def test_recursive_split_by_paragraph(processor):
    """Should split by double newline first."""
    text = "A" * 60 + "\n\n" + "B" * 60 + "\n\n" + "C" * 60
    result = processor._recursive_split(text, ["\n\n", "\n", ". "], 100)
    assert len(result) >= 2


def test_recursive_split_by_sentence(processor):
    """Should split by sentence when paragraphs are too long."""
    text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
    result = processor._recursive_split(text, ["\n\n", "\n", ". ", " "], 30)
    assert len(result) >= 2


# ===========================================================================
# Test: _add_overlap
# ===========================================================================


def test_add_overlap_empty(processor):
    """Empty list should return empty list."""
    assert processor._add_overlap([], 20) == []


def test_add_overlap_single_chunk(processor):
    """Single chunk should be returned unchanged."""
    result = processor._add_overlap(["Only one chunk"], 20)
    assert result == ["Only one chunk"]


def test_add_overlap_adds_context(processor):
    """Second chunk should start with end of first chunk."""
    chunks = ["First chunk content here", "Second chunk content here"]
    result = processor._add_overlap(chunks, 10)
    assert len(result) == 2
    assert result[0] == "First chunk content here"
    assert result[1].startswith("ntent here")


# ===========================================================================
# Test: GROBID availability check
# ===========================================================================


@pytest.mark.asyncio
async def test_grobid_unavailable(processor):
    """is_grobid_available should return False when no GROBID server."""
    available = await processor.is_grobid_available()
    assert available is False

    await processor.close()
