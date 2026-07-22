"""
===============================================================================
                    INGEST API ROUTER - DOCUMENTATION
===============================================================================

Module: app/api/ingest.py
Purpose: REST API endpoints for ingesting papers into the vector store

===============================================================================
                         ROUTER OVERVIEW
===============================================================================

This router handles the data pipeline - getting papers from PDFs into
the searchable vector store:

┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGEST ROUTER ENDPOINTS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   INGEST ENDPOINTS                                                          │
│   ────────────────                                                          │
│   POST /ingest/pdf               Upload and index local PDF                │
│   POST /ingest/arxiv/{id}        Download and index arXiv paper            │
│   POST /ingest/batch/arxiv       Batch ingest multiple arXiv papers        │
│                                                                             │
│   MANAGEMENT ENDPOINTS                                                      │
│   ────────────────────                                                      │
│   DELETE /ingest/paper/{id}      Delete paper from index                   │
│   POST /ingest/create-index      Create IVF-PQ index for scaling           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                    INGESTION PIPELINE VISUALIZATION
===============================================================================

                         PDF File / arXiv ID
                                │
                                ▼
          ┌─────────────────────────────────────────┐
          │           SAVE PDF TO DISK              │
          │         data/pdfs/{paper_id}.pdf        │
          └────────────────┬────────────────────────┘
                           │
                           ▼
          ┌─────────────────────────────────────────┐
          │        EXTRACT METADATA (GROBID)        │
          │    Title, Authors, Abstract, Refs       │
          │        TEI-XML → Structured Data        │
          └────────────────┬────────────────────────┘
                           │
                           ▼
          ┌─────────────────────────────────────────┐
          │        EXTRACT TEXT (PyMuPDF4LLM)       │
          │      PDF → Markdown (0.12s/doc)         │
          └────────────────┬────────────────────────┘
                           │
                           ▼
          ┌─────────────────────────────────────────┐
          │           CREATE CHUNKS                 │
          │     1000 chars, 200 overlap             │
          │   Recursive text splitter               │
          └────────────────┬────────────────────────┘
                           │
                           ▼
          ┌─────────────────────────────────────────┐
          │        GENERATE EMBEDDINGS              │
          │   BGE-M3 → 1024-dim vectors             │
          │    Batch processing for speed           │
          └────────────────┬────────────────────────┘
                           │
                           ▼
          ┌─────────────────────────────────────────┐
          │         STORE IN LANCEDB               │
          │    Chunks table (PyArrow schema)        │
          │     With metadata for filtering         │
          └─────────────────────────────────────────┘

===============================================================================
                    FILE STORAGE STRUCTURE
===============================================================================

data/
├── pdfs/                    # Original PDF files
│   ├── 2301.08422.pdf
│   ├── 2305.12345.pdf
│   └── ...
│
├── markdown/                # Extracted text as Markdown
│   ├── 2301.08422.md
│   ├── 2305.12345.md
│   └── ...
│
├── metadata/                # GROBID-extracted metadata (JSON)
│   ├── 2301.08422.json
│   └── ...
│
└── lancedb/                 # Vector database
    └── papers.lance/        # LanceDB table
        ├── chunks/          # Chunk vectors
        └── cache/           # Semantic cache

===============================================================================
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from pathlib import Path
# Path: Object-oriented filesystem paths
# Used for: File operations (save PDF, markdown)

from typing import Optional
# Optional: Type hint for values that can be None

# =============================================================================
# THIRD-PARTY IMPORTS: FastAPI
# =============================================================================

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile, File
# APIRouter: FastAPI router for organizing endpoints
#
# HTTPException: Raise HTTP error responses
#   - status_code: HTTP status (404, 400, etc.)
#   - detail: Error message
#
# UploadFile: Handle file uploads
#   - filename: Original filename
#   - read(): Read file contents
#   - Automatic cleanup on request completion
#
# File(...): Mark parameter as file upload
#   - ...: Required (no default)
#   - Can specify validators
#
# BackgroundTasks: Run tasks after response
#   - Useful for long-running operations
#   - Response returned before task completes

# =============================================================================
# LOCAL IMPORTS
# =============================================================================

from app.core.config import get_settings
# get_settings(): Load application configuration
# Provides: pdfs_dir, markdown_dir, etc.

from app.services.pdf_processor import get_pdf_processor
# get_pdf_processor(): Singleton PDF processor
# Handles: GROBID extraction, PyMuPDF4LLM, chunking

from app.services.vectorstore import get_vectorstore_service
# get_vectorstore_service(): Singleton vector store
# Handles: LanceDB operations, embedding storage

from app.services.apis import ArxivClient, OpenAlexClient
# API clients for fetching papers
# ArxivClient: Download PDFs and metadata from arXiv

# =============================================================================
# ROUTER CONFIGURATION
# =============================================================================

router = APIRouter(
    prefix="/ingest",
    # prefix: All routes start with /ingest
    # Full path: /api/ingest/... (after main.py adds /api)

    tags=["ingest"],
    # tags: Groups endpoints in OpenAPI docs under "ingest"
)


# =============================================================================
# ENDPOINT: INGEST PDF FILE
# =============================================================================

@router.post("/pdf")
async def ingest_pdf(
    request: Request,
    file: UploadFile = File(...),
    # file: The uploaded PDF file (required)
    # File(...) marks this as file upload, not form field

    paper_id: Optional[str] = None,
    # paper_id: Optional custom ID for the paper
    # If not provided, uses filename stem

    use_grobid: bool = True,
    # use_grobid: Whether to use GROBID for metadata
    # True: Better metadata but requires GROBID server
    # False: Fallback to filename-based metadata
) -> dict:
    """
    Ingest a PDF file into the vector store.

    Pipeline:
    1. Save PDF to disk
    2. Extract metadata with GROBID (if available)
    3. Extract text with PyMuPDF4LLM
    4. Create chunks (1000 chars, 200 overlap)
    5. Generate embeddings with BGE-M3
    6. Store in LanceDB

    This is the primary endpoint for adding local PDFs to your
    scientific library. It handles the complete pipeline from
    raw PDF to searchable chunks.

    Request (multipart/form-data):
    ──────────────────────────────
    - file: PDF file (required)
    - paper_id: Custom identifier (optional)
    - use_grobid: Use GROBID for metadata (default: true)

    Response:
    ─────────
    ```json
    {
      "paper_id": "attention_paper",
      "pdf_path": "/app/data/pdfs/attention_paper.pdf",
      "markdown_path": "/app/data/markdown/attention_paper.md",
      "chunks_count": 42,
      "indexed_chunks": 42,
      "grobid_used": true,
      "metadata": {
        "title": "Attention Is All You Need",
        "authors": ["Vaswani et al."],
        "year": 2017
      }
    }
    ```

    GROBID Behavior:
    ────────────────
    - If use_grobid=true and GROBID available:
      - Extracts: title, authors, abstract, references
      - Higher quality metadata
    - If GROBID unavailable or use_grobid=false:
      - Falls back to filename-based ID
      - Text still extracted with PyMuPDF4LLM

    cURL Example:
    ─────────────
    curl -X POST "http://localhost:3690/api/ingest/pdf" \
         -F "file=@paper.pdf" \
         -F "paper_id=my_paper" \
         -F "use_grobid=true"

    Processing Time:
    ────────────────
    - Small PDF (10 pages): ~5 seconds
    - Large PDF (100 pages): ~30 seconds
    - Most time spent on: GROBID + embedding generation
    """
    # ─────────────────────────────────────────────────────────────────────────
    # Load services
    # ─────────────────────────────────────────────────────────────────────────
    settings = get_settings()
    processor = get_pdf_processor()  # Singleton PDF processor
    vectorstore = get_vectorstore_service()  # Singleton vector store

    # ─────────────────────────────────────────────────────────────────────────
    # Generate paper_id from filename if not provided
    # ─────────────────────────────────────────────────────────────────────────
    if not paper_id:
        paper_id = Path(file.filename).stem
        # stem: Filename without extension
        # "paper.pdf" → "paper"

    # ─────────────────────────────────────────────────────────────────────────
    # Save PDF to disk
    # ─────────────────────────────────────────────────────────────────────────
    pdf_path = settings.pdfs_dir / f"{paper_id}.pdf"
    content = await file.read()
    # read(): Get raw bytes from uploaded file

    pdf_path.write_bytes(content)
    # write_bytes(): Save binary content to file
    # Overwrites if exists

    # ─────────────────────────────────────────────────────────────────────────
    # Process PDF (extract text, create chunks)
    # ─────────────────────────────────────────────────────────────────────────
    result = await processor.process_pdf(
        pdf_path=pdf_path,
        paper_id=paper_id,
        use_grobid=use_grobid,
    )
    # process_pdf returns:
    # - text: Full markdown text
    # - chunks: List of chunk dicts
    # - metadata: PaperMetadata or None
    # - grobid_used: Whether GROBID was actually used

    # ─────────────────────────────────────────────────────────────────────────
    # Save markdown version
    # ─────────────────────────────────────────────────────────────────────────
    if result["text"]:
        md_path = settings.markdown_dir / f"{paper_id}.md"
        md_path.write_text(result["text"])
        result["markdown_path"] = str(md_path)
        # Store path in result for response

    # ─────────────────────────────────────────────────────────────────────────
    # Index chunks in vector store
    # ─────────────────────────────────────────────────────────────────────────
    if result["chunks"]:
        count = vectorstore.add_chunks(result["chunks"])
        # add_chunks():
        # 1. Generate embeddings for each chunk
        # 2. Store in LanceDB with metadata
        result["indexed_chunks"] = count

    # ─────────────────────────────────────────────────────────────────────────
    # Build response
    # ─────────────────────────────────────────────────────────────────────────
    response = {
        "paper_id": paper_id,
        "pdf_path": str(pdf_path),
        "markdown_path": result.get("markdown_path"),
        "chunks_count": len(result["chunks"]),
        "indexed_chunks": result.get("indexed_chunks", 0),
        "grobid_used": result["grobid_used"],
        "metadata": result["metadata"].model_dump() if result["metadata"] else None,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Publish event to vital-core (fire-and-forget)
    # ─────────────────────────────────────────────────────────────────────────
    vital_client = getattr(request.app.state, "vital_client", None)
    if vital_client is not None:
        await vital_client.publish_event(
            category="education",
            action="create",
            event_type="paper.ingested",
            payload={
                "paper_id": paper_id,
                "chunks_count": response["chunks_count"],
                "grobid_used": response["grobid_used"],
            },
            tags=["research", "ingestion"],
        )

    return response


# =============================================================================
# ENDPOINT: INGEST ARXIV PAPER
# =============================================================================

@router.post("/arxiv/{arxiv_id}")
async def ingest_arxiv_paper(
    request: Request,
    arxiv_id: str,
    # arxiv_id: arXiv paper identifier
    # Examples: "2301.08422", "hep-th/9901001"

    use_grobid: bool = True,
    # use_grobid: Use GROBID for additional metadata
) -> dict:
    """
    Download and ingest paper from arXiv.

    1. Fetch metadata from arXiv API
    2. Download PDF
    3. Process and index

    This endpoint automates the full workflow for arXiv papers:
    - Fetches metadata (title, authors, abstract, categories)
    - Downloads the PDF
    - Processes and indexes like /ingest/pdf

    Path Parameter:
    ───────────────
    - arxiv_id: arXiv identifier (e.g., "2301.08422")

    Query Parameters:
    ─────────────────
    - use_grobid: Use GROBID for metadata (default: true)

    Response:
    ─────────
    ```json
    {
      "arxiv_id": "2301.08422",
      "paper_id": "2301.08422",
      "title": "Paper Title",
      "authors": ["Author 1", "Author 2"],
      "categories": ["cs.LG", "cs.AI"],
      "pdf_path": "/app/data/pdfs/2301.08422.pdf",
      "markdown_path": "/app/data/markdown/2301.08422.md",
      "chunks_count": 35,
      "indexed_chunks": 35
    }
    ```

    Metadata Enhancement:
    ─────────────────────
    Chunks are enriched with arXiv metadata:
    - Title from arXiv (not GROBID)
    - Authors from arXiv
    - arXiv categories for filtering
    - Year from publication date

    This enables queries like:
    - Filter by category (cs.LG, physics.quant-ph)
    - Filter by year range
    - Search within specific author's papers

    Rate Limiting:
    ──────────────
    arXiv requires 3 seconds between requests.
    Ingesting multiple papers sequentially will be slow.
    For bulk ingestion, use /ingest/batch/arxiv.

    Example:
    ────────
    POST /api/ingest/arxiv/2301.08422
    """
    settings = get_settings()
    arxiv_client = ArxivClient()
    processor = get_pdf_processor()
    vectorstore = get_vectorstore_service()

    try:
        # ─────────────────────────────────────────────────────────────────────
        # Fetch metadata from arXiv API
        # ─────────────────────────────────────────────────────────────────────
        entry = await arxiv_client.get_by_id(arxiv_id)
        if not entry:
            raise HTTPException(status_code=404, detail="arXiv paper not found")

        metadata = arxiv_client.entry_to_metadata(entry)
        # Convert arXiv entry to PaperMetadata
        # Contains: title, authors, abstract, categories, pdf_url

        # ─────────────────────────────────────────────────────────────────────
        # Download PDF
        # ─────────────────────────────────────────────────────────────────────
        pdf_content = await arxiv_client.download_pdf(arxiv_id)
        # download_pdf() returns raw bytes
        # arXiv rate limiting handled by client

        # Sanitize ID for filename (replace / with _)
        clean_id = arxiv_id.replace("/", "_")
        pdf_path = settings.pdfs_dir / f"{clean_id}.pdf"
        pdf_path.write_bytes(pdf_content)

        # ─────────────────────────────────────────────────────────────────────
        # Process PDF
        # ─────────────────────────────────────────────────────────────────────
        result = await processor.process_pdf(
            pdf_path=pdf_path,
            paper_id=clean_id,
            use_grobid=use_grobid,
        )

        # ─────────────────────────────────────────────────────────────────────
        # Enhance chunks with arXiv metadata
        # ─────────────────────────────────────────────────────────────────────
        for chunk in result["chunks"]:
            # Override with authoritative arXiv metadata
            chunk["title"] = metadata.title
            chunk["year"] = metadata.year
            chunk["authors"] = [a.name for a in metadata.authors]
            chunk["arxiv_id"] = arxiv_id
            chunk["arxiv_categories"] = metadata.arxiv_categories
            # arXiv categories enable filtering by field

        # ─────────────────────────────────────────────────────────────────────
        # Save markdown
        # ─────────────────────────────────────────────────────────────────────
        md_path = settings.markdown_dir / f"{clean_id}.md"
        md_path.write_text(result["text"])

        # ─────────────────────────────────────────────────────────────────────
        # Index chunks
        # ─────────────────────────────────────────────────────────────────────
        count = vectorstore.add_chunks(result["chunks"])

        # ─────────────────────────────────────────────────────────────────────
        # Build response
        # ─────────────────────────────────────────────────────────────────────
        response = {
            "arxiv_id": arxiv_id,
            "paper_id": clean_id,
            "title": metadata.title,
            "authors": [a.name for a in metadata.authors],
            "categories": metadata.arxiv_categories,
            "pdf_path": str(pdf_path),
            "markdown_path": str(md_path),
            "chunks_count": len(result["chunks"]),
            "indexed_chunks": count,
        }

        # Publish event to vital-core (fire-and-forget)
        vital_client = getattr(request.app.state, "vital_client", None)
        if vital_client is not None:
            await vital_client.publish_event(
                category="education",
                action="create",
                event_type="paper.ingested",
                payload={
                    "paper_id": clean_id,
                    "arxiv_id": arxiv_id,
                    "title": metadata.title,
                    "chunks_count": response["chunks_count"],
                },
                tags=["research", "ingestion", "arxiv"],
            )

        return response

    finally:
        await arxiv_client.close()


# =============================================================================
# ENDPOINT: BATCH INGEST ARXIV PAPERS
# =============================================================================

@router.post("/batch/arxiv")
async def ingest_arxiv_batch(
    arxiv_ids: list[str],
    # arxiv_ids: List of arXiv paper IDs to ingest

    use_grobid: bool = True,
    # use_grobid: Use GROBID for metadata extraction
) -> dict:
    """
    Batch ingest multiple papers from arXiv.

    This endpoint processes multiple arXiv papers in sequence.
    Failed papers are recorded but don't stop the batch.

    Request Body:
    ─────────────
    ```json
    {
      "arxiv_ids": ["2301.08422", "2305.12345", "2310.98765"],
      "use_grobid": true
    }
    ```

    Response:
    ─────────
    ```json
    {
      "total": 3,
      "success": 2,
      "failed": 1,
      "results": [
        {"arxiv_id": "2301.08422", "title": "...", "chunks_count": 35},
        {"arxiv_id": "2305.12345", "title": "...", "chunks_count": 42}
      ],
      "errors": [
        {"arxiv_id": "2310.98765", "error": "arXiv paper not found"}
      ]
    }
    ```

    Processing Time:
    ────────────────
    Due to arXiv's 3-second rate limit:
    - 10 papers: ~30 seconds download + processing
    - 100 papers: ~5 minutes download + processing

    For very large batches, consider:
    1. Using arXiv's bulk data on S3
    2. Running multiple ingestion processes
    3. Caching already-downloaded PDFs

    Error Handling:
    ───────────────
    - Individual failures don't stop the batch
    - Errors are collected and returned
    - Successfully ingested papers remain in index

    Example:
    ────────
    curl -X POST "http://localhost:3690/api/ingest/batch/arxiv" \
         -H "Content-Type: application/json" \
         -d '{"arxiv_ids": ["2301.08422", "2305.12345"]}'
    """
    results = []  # Successfully processed papers
    errors = []   # Failed papers with error messages

    for arxiv_id in arxiv_ids:
        try:
            # ─────────────────────────────────────────────────────────────────
            # Ingest each paper individually
            # ─────────────────────────────────────────────────────────────────
            result = await ingest_arxiv_paper(arxiv_id, use_grobid)
            results.append(result)

        except Exception as e:
            # ─────────────────────────────────────────────────────────────────
            # Record error and continue
            # ─────────────────────────────────────────────────────────────────
            errors.append({
                "arxiv_id": arxiv_id,
                "error": str(e),
            })
            # Continue to next paper - don't fail entire batch

    # ─────────────────────────────────────────────────────────────────────────
    # Build summary response
    # ─────────────────────────────────────────────────────────────────────────
    return {
        "total": len(arxiv_ids),
        "success": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


# =============================================================================
# ENDPOINT: ASYNC INGEST PDF (BackgroundTasks)
# =============================================================================

def _ingest_pdf_background(
    pdf_path: Path,
    paper_id: str,
    use_grobid: bool,
) -> None:
    """Run PDF ingestion in a background task."""
    import asyncio

    async def _run():
        settings = get_settings()
        processor = get_pdf_processor()
        vectorstore = get_vectorstore_service()

        result = await processor.process_pdf(
            pdf_path=pdf_path,
            paper_id=paper_id,
            use_grobid=use_grobid,
        )

        if result["text"]:
            md_path = settings.markdown_dir / f"{paper_id}.md"
            md_path.write_text(result["text"])

        if result["chunks"]:
            vectorstore.add_chunks(result["chunks"])

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


@router.post("/pdf/async")
async def ingest_pdf_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    paper_id: Optional[str] = None,
    use_grobid: bool = True,
) -> dict:
    """
    Ingest a PDF file in the background.

    Returns immediately with accepted status while processing continues.
    Useful for large PDFs that would otherwise timeout.
    """
    settings = get_settings()

    if not paper_id:
        paper_id = Path(file.filename).stem

    pdf_path = settings.pdfs_dir / f"{paper_id}.pdf"
    content = await file.read()
    pdf_path.write_bytes(content)

    background_tasks.add_task(
        _ingest_pdf_background,
        pdf_path=pdf_path,
        paper_id=paper_id,
        use_grobid=use_grobid,
    )

    return {
        "status": "accepted",
        "paper_id": paper_id,
        "pdf_path": str(pdf_path),
        "message": "PDF ingestion started in background",
    }


# =============================================================================
# ENDPOINT: DELETE PAPER
# =============================================================================

@router.delete("/paper/{paper_id}")
async def delete_paper(paper_id: str) -> dict:
    """
    Delete a paper and its chunks from the vector store.

    This endpoint removes:
    1. Chunks from LanceDB vector store
    2. PDF file from disk
    3. Markdown file from disk

    Path Parameter:
    ───────────────
    - paper_id: The paper's identifier

    Response:
    ─────────
    ```json
    {
      "paper_id": "2301.08422",
      "files_deleted": [
        "/app/data/pdfs/2301.08422.pdf",
        "/app/data/markdown/2301.08422.md"
      ]
    }
    ```

    Note:
    ─────
    - If paper not in index, no error raised
    - Files are deleted if they exist
    - Operation is irreversible

    Example:
    ────────
    DELETE /api/ingest/paper/2301.08422
    """
    settings = get_settings()
    vectorstore = get_vectorstore_service()

    # ─────────────────────────────────────────────────────────────────────────
    # Delete from vector store
    # ─────────────────────────────────────────────────────────────────────────
    vectorstore.delete_paper(paper_id)
    # delete_paper() removes all chunks with matching paper_id
    # Uses LanceDB's delete functionality

    # ─────────────────────────────────────────────────────────────────────────
    # Delete files from disk
    # ─────────────────────────────────────────────────────────────────────────
    pdf_path = settings.pdfs_dir / f"{paper_id}.pdf"
    md_path = settings.markdown_dir / f"{paper_id}.md"

    files_deleted = []

    if pdf_path.exists():
        pdf_path.unlink()  # Delete file
        files_deleted.append(str(pdf_path))

    if md_path.exists():
        md_path.unlink()
        files_deleted.append(str(md_path))

    # ─────────────────────────────────────────────────────────────────────────
    # Return summary
    # ─────────────────────────────────────────────────────────────────────────
    return {
        "paper_id": paper_id,
        "files_deleted": files_deleted,
    }


# =============================================================================
# ENDPOINT: CREATE VECTOR INDEX
# =============================================================================

@router.post("/create-index")
async def create_vector_index(
    num_partitions: int = 256,
    # num_partitions: Number of IVF partitions
    # More partitions = faster search, more memory
    # Recommended: sqrt(num_vectors) to 4*sqrt(num_vectors)

    num_sub_vectors: int = 96,
    # num_sub_vectors: PQ sub-vector count
    # More = higher quality, larger index
    # Must divide vector dimension (1024 / 96 ≈ 10.7 → use 96)
) -> dict:
    """
    Create IVF-PQ index for large collections.

    Recommended for 1M+ papers.
    Parameters from guide: 256 partitions, 96 sub-vectors.

    For small collections (<10K papers), flat search is fast enough.
    For large collections, IVF-PQ provides:
    - 10-100x faster search
    - ~10x smaller index size
    - Slight accuracy trade-off (~95% recall)

    Request Parameters:
    ───────────────────
    - num_partitions: IVF partition count (default 256)
    - num_sub_vectors: PQ compression factor (default 96)

    Response:
    ─────────
    ```json
    {
      "message": "Index created",
      "num_partitions": 256,
      "num_sub_vectors": 96
    }
    ```

    When to Create Index:
    ─────────────────────
    - After initial bulk ingestion
    - When search becomes slow (>100ms)
    - When you have 100K+ chunks

    Index Parameters:
    ─────────────────
    num_partitions (IVF):
    - Inverted File Index partitions
    - Search only visits ~10% of partitions
    - More partitions = faster search, more memory
    - Rule of thumb: sqrt(num_vectors)

    num_sub_vectors (PQ):
    - Product Quantization compression
    - Divides 1024-dim vector into sub-vectors
    - Each sub-vector → 1 byte
    - 96 sub-vectors: 1024/96 ≈ 10-11 dims each

    Example:
    ────────
    POST /api/ingest/create-index
    {"num_partitions": 256, "num_sub_vectors": 96}
    """
    vectorstore = get_vectorstore_service()

    vectorstore.create_index(
        num_partitions=num_partitions,
        num_sub_vectors=num_sub_vectors,
    )
    # create_index() calls LanceDB's create_index()
    # Builds IVF-PQ index on the chunks table
    # May take several minutes for large collections

    return {
        "message": "Index created",
        "num_partitions": num_partitions,
        "num_sub_vectors": num_sub_vectors,
    }


# =============================================================================
#                         USAGE NOTES
# =============================================================================
#
# INGESTION BEST PRACTICES:
# ─────────────────────────
# 1. Use GROBID when available (better metadata)
# 2. Use arXiv endpoint when possible (includes categories)
# 3. Create index after bulk ingestion
# 4. Monitor disk space (PDFs + markdown can be large)
#
# ERROR HANDLING:
# ───────────────
# - 404: Paper not found (arXiv/OpenAlex)
# - 500: Processing error (check GROBID, Ollama)
# - Timeout: Large PDF or slow embedding
#
# SCALING CONSIDERATIONS:
# ───────────────────────
# - For >1M papers: Use IVF-PQ index
# - For bulk ingestion: Use batch endpoint
# - For very large PDFs: Increase timeout
# =============================================================================
