"""
===============================================================================
                      FASTAPI ROUTERS MODULE - DOCUMENTATION
===============================================================================

Module: app/api/__init__.py
Purpose: Central registry for all FastAPI API routers

===============================================================================
                         API ARCHITECTURE OVERVIEW
===============================================================================

This module organizes the Scientific Library RAG system's REST API into
logical routers, each handling a specific domain:

┌─────────────────────────────────────────────────────────────────────────────┐
│                      API ROUTER ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   FastAPI App (main.py)                                                     │
│       │                                                                     │
│       └── app.include_router(router, prefix="/api")                        │
│           │                                                                 │
│           ├── papers_router ──────► /api/papers/*                          │
│           │   └── Search, fetch, download papers from external APIs        │
│           │                                                                 │
│           ├── rag_router ─────────► /api/rag/*                             │
│           │   └── RAG queries, streaming, semantic search                   │
│           │                                                                 │
│           ├── ingest_router ──────► /api/ingest/*                          │
│           │   └── PDF processing, indexing, batch operations               │
│           │                                                                 │
│           └── search_router ──────► /api/search/*                          │
│               └── Vector search, Nobel, Fields Medal, Turing               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                    COMPLETE ENDPOINT REFERENCE
===============================================================================

┌────────────────────────────────────────────────────────────────────────────┐
│                         PAPERS ROUTER (/api/papers)                        │
├────────────────────────────────────────────────────────────────────────────┤
│ GET  /papers/search/openalex?query=...  Search OpenAlex (240M papers)     │
│ GET  /papers/search/arxiv?query=...     Search arXiv (2.5M preprints)     │
│ GET  /papers/by-doi/{doi}               Get paper by DOI                   │
│ GET  /papers/by-arxiv/{arxiv_id}        Get paper by arXiv ID             │
│ GET  /papers/oa-url/{doi}               Find OA PDF via Unpaywall         │
│ POST /papers/download/arxiv/{arxiv_id}  Download arXiv PDF                │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                           RAG ROUTER (/api/rag)                            │
├────────────────────────────────────────────────────────────────────────────┤
│ POST /rag/query           RAG query → answer + sources                     │
│ POST /rag/query/stream    RAG with SSE streaming                           │
│ GET  /rag/search          Search without generation                        │
│ GET  /rag/ask?question=   Simple GET for quick queries                     │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                        INGEST ROUTER (/api/ingest)                         │
├────────────────────────────────────────────────────────────────────────────┤
│ POST /ingest/pdf              Upload & index PDF                           │
│ POST /ingest/arxiv/{id}       Download & index arXiv paper                 │
│ POST /ingest/batch/arxiv      Batch ingest multiple papers                 │
│ DELETE /ingest/paper/{id}     Delete paper from index                      │
│ POST /ingest/create-index     Create IVF-PQ index for scaling              │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                       SEARCH ROUTER (/api/search)                          │
├────────────────────────────────────────────────────────────────────────────┤
│ GET  /search/papers             Vector search in local index               │
│ GET  /search/nobel              Nobel Prize laureates                      │
│ GET  /search/fields-medal       Fields Medal winners                       │
│ GET  /search/turing-award       Turing Award winners                       │
│ GET  /search/abel-prize         Abel Prize winners                         │
│ GET  /search/prizes/{qid}       Any prize by Wikidata Q-ID                │
│ GET  /search/scientist/{qid}/prizes  All prizes for a scientist           │
└────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                         ROUTER DESIGN PATTERNS
===============================================================================

1. SINGLE RESPONSIBILITY
   ──────────────────────
   Each router handles ONE domain:
   - papers_router: External paper APIs
   - rag_router: AI/LLM operations
   - ingest_router: Data pipeline
   - search_router: Query operations

2. DEPENDENCY INJECTION via get_*_service()
   ─────────────────────────────────────────
   Services are singletons via @lru_cache:
   ```python
   from app.services.rag import get_rag_service
   service = get_rag_service()  # Always same instance
   ```

3. ASYNC CONTEXT MANAGERS for API Clients
   ───────────────────────────────────────
   External API clients use try/finally pattern:
   ```python
   client = OpenAlexClient()
   try:
       result = await client.search_works(...)
   finally:
       await client.close()
   ```

4. PYDANTIC MODELS for Request/Response
   ─────────────────────────────────────
   ```python
   @router.post("/query", response_model=RAGResponse)
   async def rag_query(request: RAGQuery) -> RAGResponse:
       ...
   ```

5. QUERY PARAMETERS with Validation
   ─────────────────────────────────
   ```python
   @router.get("/search")
   async def search(
       query: str,
       top_k: int = Query(default=10, ge=1, le=100),
       year_min: Optional[int] = None,
   ):
       ...
   ```

===============================================================================
                         USAGE EXAMPLES
===============================================================================

cURL Examples:
──────────────

# Search OpenAlex
curl "http://localhost:3690/api/papers/search/openalex?query=transformer&limit=10"

# RAG Query
curl -X POST "http://localhost:3690/api/rag/query" \
     -H "Content-Type: application/json" \
     -d '{"question": "What is attention mechanism?"}'

# Upload PDF
curl -X POST "http://localhost:3690/api/ingest/pdf" \
     -F "file=@paper.pdf" \
     -F "use_grobid=true"

# Search Nobel laureates
curl "http://localhost:3690/api/search/nobel?category=physics&year_from=2020"

Python Examples:
────────────────

```python
import httpx

async with httpx.AsyncClient(base_url="http://localhost:3690/api") as client:
    # RAG query
    response = await client.post("/rag/query", json={
        "question": "Explain transformers",
        "top_k": 10,
    })
    print(response.json())

    # Search papers
    response = await client.get("/papers/search/openalex", params={
        "query": "machine learning",
        "limit": 25,
        "open_access": True,
    })
    papers = response.json()
```

===============================================================================
"""

# =============================================================================
# ROUTER IMPORTS
# =============================================================================

from app.api.papers import router as papers_router
# papers_router: External paper API endpoints
# Prefix: /papers
# Features: OpenAlex search, arXiv search, DOI lookup, PDF download

from app.api.rag import router as rag_router
# rag_router: RAG query and search endpoints
# Prefix: /rag
# Features: Question answering, streaming, semantic search

from app.api.ingest import router as ingest_router
# ingest_router: Document ingestion endpoints
# Prefix: /ingest
# Features: PDF upload, arXiv ingest, batch processing, indexing

from app.api.search import router as search_router
# search_router: Search and discovery endpoints
# Prefix: /search
# Features: Vector search, Nobel Prize, Fields Medal, Turing Award

from app.api.instagram import router as instagram_router
# instagram_router: Instagram content automation
# Prefix: /instagram
# Features: Draft generation, image rendering, approval flow, IG publish

# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    "papers_router",     # /papers - External paper APIs
    "rag_router",        # /rag - AI/LLM operations
    "ingest_router",     # /ingest - Document pipeline
    "search_router",     # /search - Query operations
    "instagram_router",  # /instagram - Content automation
]

# =============================================================================
# ROUTER REGISTRATION (in main.py)
# =============================================================================
#
# from fastapi import FastAPI
# from app.api import papers_router, rag_router, ingest_router, search_router
#
# app = FastAPI(title="Scientific Library RAG")
#
# # Register all routers under /api prefix
# for router in [papers_router, rag_router, ingest_router, search_router]:
#     app.include_router(router, prefix="/api")
#
# # Results in:
# # - /api/papers/...
# # - /api/rag/...
# # - /api/ingest/...
# # - /api/search/...
# =============================================================================
