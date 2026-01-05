"""
===============================================================================
                    PAPERS API ROUTER - DOCUMENTATION
===============================================================================

Module: app/api/papers.py
Purpose: REST API endpoints for searching and fetching papers from external APIs

===============================================================================
                         ROUTER OVERVIEW
===============================================================================

This router provides access to external scientific paper databases:

┌─────────────────────────────────────────────────────────────────────────────┐
│                         PAPERS ROUTER ENDPOINTS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   SEARCH ENDPOINTS                                                          │
│   ────────────────                                                          │
│   GET /papers/search/openalex   Search 240M papers via OpenAlex            │
│   GET /papers/search/arxiv      Search 2.5M preprints via arXiv            │
│                                                                             │
│   LOOKUP ENDPOINTS                                                          │
│   ────────────────                                                          │
│   GET /papers/by-doi/{doi}      Get paper by DOI (via OpenAlex)            │
│   GET /papers/by-arxiv/{id}     Get paper by arXiv ID                      │
│   GET /papers/oa-url/{doi}      Find OA URL via Unpaywall                  │
│                                                                             │
│   DOWNLOAD ENDPOINTS                                                        │
│   ──────────────────                                                        │
│   POST /papers/download/arxiv/{id}  Download arXiv PDF to disk             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                     DATA FLOW DIAGRAM
===============================================================================

                        User Request
                             │
                             ▼
                   ┌─────────────────┐
                   │ FastAPI Router  │
                   │  /api/papers    │
                   └────────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
  ┌──────────┐       ┌──────────┐       ┌──────────────┐
  │ OpenAlex │       │  arXiv   │       │  Unpaywall   │
  │  Client  │       │  Client  │       │   Client     │
  │ 10 req/s │       │ 1 req/3s │       │ 100K req/day │
  └────┬─────┘       └────┬─────┘       └──────┬───────┘
       │                  │                    │
       ▼                  ▼                    ▼
  ┌──────────┐       ┌──────────┐       ┌──────────────┐
  │  240M+   │       │  2.5M+   │       │    47M+ OA   │
  │  Papers  │       │ Preprints│       │   Articles   │
  └────┬─────┘       └────┬─────┘       └──────┬───────┘
       │                  │                    │
       └──────────────────┼────────────────────┘
                          │
                          ▼
               ┌──────────────────┐
               │  PaperMetadata   │
               │  (normalized)    │
               └────────┬─────────┘
                        │
                        ▼
                 JSON Response

===============================================================================
                    WHY SEPARATE SEARCH APIs?
===============================================================================

Each external API has different strengths:

┌──────────────┬────────────────────────────────────────────────────────────┐
│ OpenAlex     │ Best for: General discovery, citation data, metadata       │
│              │ - 240M papers (largest)                                    │
│              │ - Citation counts, concepts, institutions                  │
│              │ - 10 req/s (fast)                                          │
├──────────────┼────────────────────────────────────────────────────────────┤
│ arXiv        │ Best for: Preprints, direct PDF access, physics/CS/math   │
│              │ - 2.5M preprints (growing fast)                            │
│              │ - Full PDF available immediately                           │
│              │ - 1 req/3s (slow but free PDFs)                            │
├──────────────┼────────────────────────────────────────────────────────────┤
│ Unpaywall    │ Best for: Finding legal OA versions by DOI                │
│              │ - 47M OA articles indexed                                  │
│              │ - Points to repositories, publisher OA, preprints          │
│              │ - 100K req/day (generous)                                  │
└──────────────┴────────────────────────────────────────────────────────────┘

Typical Workflow:
1. Search OpenAlex for papers on a topic
2. Get DOIs from results
3. Check Unpaywall for OA PDFs
4. Or search arXiv for preprints with direct PDF

===============================================================================
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from pathlib import Path
# Path: Object-oriented filesystem paths
# Used for: PDF file path operations (save downloaded PDFs)

from typing import Optional
# Optional: Type hint for values that can be None
# Used for: Optional query parameters (year, category)

# =============================================================================
# THIRD-PARTY IMPORTS: FastAPI
# =============================================================================

from fastapi import APIRouter, HTTPException, Query
# APIRouter: FastAPI router for organizing endpoints
#   - Groups related endpoints
#   - Applies common prefix and tags
#   - Can have dependencies shared across endpoints
#
# HTTPException: Raise HTTP error responses
#   - status_code: HTTP status (404, 400, 500, etc.)
#   - detail: Error message to return
#
# Query: Validate and document query parameters
#   - default: Default value if not provided
#   - ge, le: Greater/less than or equal (for numbers)
#   - description: OpenAPI documentation

# =============================================================================
# LOCAL IMPORTS
# =============================================================================

from app.core.config import get_settings
# get_settings(): Load application configuration
# Provides: pdfs_dir, unpaywall_email, etc.

from app.models.paper import PaperMetadata
# PaperMetadata: Normalized paper model (source-agnostic)
# All external APIs convert to this format

from app.services.apis import OpenAlexClient, ArxivClient, UnpaywallClient
# API Clients for external services
# See app/services/apis/ for detailed documentation

# =============================================================================
# ROUTER CONFIGURATION
# =============================================================================

router = APIRouter(
    prefix="/papers",
    # prefix: All routes in this router start with /papers
    # Full path: /api/papers/... (after main.py adds /api prefix)

    tags=["papers"],
    # tags: Group in OpenAPI/Swagger documentation
    # Appears as section header in /docs
)


# =============================================================================
# ENDPOINT: SEARCH OPENALEX
# =============================================================================

@router.get("/search/openalex")
async def search_openalex(
    query: str,
    # query: Required search terms
    # Searches title, abstract, and full text

    limit: int = Query(default=25, ge=1, le=200),
    # limit: Results per page
    # Query() adds validation: must be 1-200
    # OpenAlex max is 200

    page: int = Query(default=1, ge=1),
    # page: Pagination (1-indexed)
    # Page 1 = results 1-limit
    # Page 2 = results limit+1 to 2*limit

    open_access: bool = False,
    # open_access: Filter to only OA papers
    # Useful for building downloadable corpus

    year: Optional[int] = None,
    # year: Filter by publication year
    # None = all years
) -> list[dict]:
    """
    Search papers via OpenAlex API.

    OpenAlex: 240M+ papers, CC0, 10 req/s with email.

    This endpoint provides access to OpenAlex, the largest free academic
    metadata database. It's ideal for:
    - Discovery: Finding papers on any topic
    - Citation analysis: Papers include citation counts
    - Concept mapping: Papers tagged with 65K concepts

    Request Parameters:
    ───────────────────
    - query (required): Search terms
    - limit (default 25): Results per page (max 200)
    - page (default 1): Pagination
    - open_access (default false): Filter to OA only
    - year (optional): Filter by exact year

    Response:
    ─────────
    List of paper metadata objects with:
    - doi, title, abstract
    - authors (with ORCIDs)
    - year, cited_by_count
    - is_open_access, pdf_url (if available)
    - concepts (topic tags)

    Example:
    ────────
    GET /api/papers/search/openalex?query=attention+mechanism&limit=10&open_access=true

    Response (truncated):
    ```json
    [
      {
        "doi": "10.48550/arXiv.1706.03762",
        "title": "Attention Is All You Need",
        "abstract": "The dominant sequence transduction...",
        "year": 2017,
        "cited_by_count": 75000,
        "is_open_access": true,
        "concepts": ["Transformer", "Attention", "Neural Network"]
      }
    ]
    ```
    """
    # ─────────────────────────────────────────────────────────────────────────
    # Create API client
    # ─────────────────────────────────────────────────────────────────────────
    client = OpenAlexClient()
    # OpenAlexClient loads email from settings for polite pool (10 req/s)

    try:
        # ─────────────────────────────────────────────────────────────────────
        # Execute search
        # ─────────────────────────────────────────────────────────────────────
        works = await client.search_works(
            query=query,
            limit=limit,
            page=page,
            filter_oa=open_access,
            filter_year=year,
        )

        # ─────────────────────────────────────────────────────────────────────
        # Convert to normalized format
        # ─────────────────────────────────────────────────────────────────────
        return [client.work_to_metadata(w).model_dump() for w in works]
        # work_to_metadata(): Convert OpenAlex response to PaperMetadata
        # model_dump(): Pydantic v2 method to convert model to dict
        # (Previously model.dict() in Pydantic v1)

    finally:
        # ─────────────────────────────────────────────────────────────────────
        # Always close client
        # ─────────────────────────────────────────────────────────────────────
        await client.close()
        # Close HTTP connection pool
        # Important for resource cleanup


# =============================================================================
# ENDPOINT: SEARCH ARXIV
# =============================================================================

@router.get("/search/arxiv")
async def search_arxiv(
    query: str,
    # query: Search terms (supports arXiv query syntax)
    # Examples: "quantum computing", "ti:attention", "au:hinton"

    max_results: int = Query(default=100, ge=1, le=1000),
    # max_results: Maximum papers to return
    # arXiv allows up to ~30000 but we limit to 1000 for sanity

    category: Optional[str] = None,
    # category: Filter by arXiv category
    # Examples: "cs.AI", "physics.quant-ph", "math.CO"
) -> list[dict]:
    """
    Search papers via arXiv API.

    arXiv: 2.5M+ papers, no auth, 1 req/3s, direct PDF access.

    This endpoint provides access to arXiv, the premier preprint server.
    Unlike OpenAlex, arXiv provides:
    - Direct PDF access (no paywall)
    - Latest research (preprints, not yet peer-reviewed)
    - Category-based filtering (physics, CS, math, etc.)

    Request Parameters:
    ───────────────────
    - query (required): Search terms
    - max_results (default 100): Maximum results (max 1000)
    - category (optional): arXiv category code (e.g., "cs.LG")

    Query Syntax:
    ─────────────
    - "quantum computing" - Words in title/abstract
    - ti:attention - Title contains "attention"
    - au:vaswani - Author name contains "vaswani"
    - cat:cs.AI - Category is cs.AI (redundant with category param)

    Response:
    ─────────
    List of paper metadata with:
    - arxiv_id, title, abstract
    - authors (names only)
    - published date, categories
    - pdf_url (direct link)
    - is_open_access: true (always for arXiv)

    Example:
    ────────
    GET /api/papers/search/arxiv?query=transformer&category=cs.LG&max_results=50

    Rate Limiting Note:
    ───────────────────
    arXiv enforces 1 request per 3 seconds. This endpoint will be slow
    for large result sets. For bulk data, use arXiv's OAI-PMH or S3 bulk.
    """
    client = ArxivClient()

    try:
        if category:
            # ─────────────────────────────────────────────────────────────────
            # Search within specific category
            # ─────────────────────────────────────────────────────────────────
            entries = await client.search_by_category(category, max_results)
            # search_by_category adds cat:{category} to query
            # and sorts by submission date
        else:
            # ─────────────────────────────────────────────────────────────────
            # General search
            # ─────────────────────────────────────────────────────────────────
            entries = await client.search(query, max_results)
            # Standard keyword search across all fields

        # ─────────────────────────────────────────────────────────────────────
        # Convert to normalized format
        # ─────────────────────────────────────────────────────────────────────
        return [client.entry_to_metadata(e).model_dump() for e in entries]

    finally:
        await client.close()


# =============================================================================
# ENDPOINT: GET PAPER BY DOI
# =============================================================================

@router.get("/by-doi/{doi:path}")
async def get_paper_by_doi(doi: str) -> dict:
    """
    Get paper metadata by DOI from OpenAlex.

    DOI (Digital Object Identifier) is the standard persistent identifier
    for academic papers. Format: 10.prefix/suffix

    Path Parameter:
    ───────────────
    - doi: The DOI string (URL path captures the slashes)
           Example: 10.1038/nature12373

    The `:path` converter in FastAPI allows slashes in the parameter,
    so both forms work:
    - /api/papers/by-doi/10.1038/nature12373
    - /api/papers/by-doi/10.1038%2Fnature12373 (URL encoded)

    Response:
    ─────────
    Paper metadata object (see search_openalex for fields)

    Errors:
    ───────
    - 404: DOI not found in OpenAlex

    Example:
    ────────
    GET /api/papers/by-doi/10.1038/nature12373

    Response:
    ```json
    {
      "doi": "10.1038/nature12373",
      "title": "Example Paper Title",
      "year": 2013,
      "cited_by_count": 5000,
      ...
    }
    ```
    """
    client = OpenAlexClient()

    try:
        work = await client.get_work_by_doi(doi)
        # get_work_by_doi uses OpenAlex's DOI endpoint
        # Much faster than search (direct lookup)

        if not work:
            raise HTTPException(
                status_code=404,
                detail="Paper not found"
            )
            # 404 Not Found if DOI not in OpenAlex
            # Could be: invalid DOI, very new paper, or not indexed

        return client.work_to_metadata(work).model_dump()

    finally:
        await client.close()


# =============================================================================
# ENDPOINT: GET PAPER BY ARXIV ID
# =============================================================================

@router.get("/by-arxiv/{arxiv_id}")
async def get_paper_by_arxiv(arxiv_id: str) -> dict:
    """
    Get paper metadata by arXiv ID.

    arXiv IDs identify papers on arxiv.org. Modern format: YYMM.NNNNN

    Path Parameter:
    ───────────────
    - arxiv_id: arXiv identifier
                New format: 2301.08422
                Old format: hep-th/9901001

    Note: IDs with slashes (old format) need URL encoding or use query param.

    Response:
    ─────────
    Paper metadata with:
    - arxiv_id, title, abstract
    - authors, published date
    - categories, pdf_url
    - doi (if published)

    Errors:
    ───────
    - 404: arXiv ID not found

    Example:
    ────────
    GET /api/papers/by-arxiv/1706.03762

    Response:
    ```json
    {
      "arxiv_id": "1706.03762",
      "title": "Attention Is All You Need",
      "abstract": "The dominant sequence transduction...",
      "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
      ...
    }
    ```
    """
    client = ArxivClient()

    try:
        entry = await client.get_by_id(arxiv_id)
        # get_by_id uses arXiv's id_list parameter
        # Handles version suffixes (v1, v2) automatically

        if not entry:
            raise HTTPException(status_code=404, detail="Paper not found")

        return client.entry_to_metadata(entry).model_dump()

    finally:
        await client.close()


# =============================================================================
# ENDPOINT: GET OPEN ACCESS URL
# =============================================================================

@router.get("/oa-url/{doi:path}")
async def get_open_access_url(doi: str) -> dict:
    """
    Find Open Access PDF URL for a DOI via Unpaywall.

    Unpaywall: 100K req/day with email.

    Unpaywall aggregates legal Open Access versions of papers from:
    - Publisher websites (gold OA)
    - Institutional repositories (green OA)
    - Preprint servers (arXiv, bioRxiv, etc.)
    - PubMed Central

    Path Parameter:
    ───────────────
    - doi: DOI to look up

    Response:
    ─────────
    ```json
    {
      "doi": "10.1038/nature12373",
      "is_oa": true,
      "pdf_url": "https://europepmc.org/articles/pmc1234567?pdf=render",
      "title": "Paper Title"
    }
    ```

    Errors:
    ───────
    - 400: Unpaywall email not configured
    - 404: DOI not found in Unpaywall

    Configuration:
    ──────────────
    Requires UNPAYWALL_EMAIL in .env file.
    This is used for rate limiting (100K/day).

    Example:
    ────────
    GET /api/papers/oa-url/10.1038/nature12373
    """
    # ─────────────────────────────────────────────────────────────────────────
    # Check configuration
    # ─────────────────────────────────────────────────────────────────────────
    settings = get_settings()

    if not settings.unpaywall_email:
        raise HTTPException(
            status_code=400,
            detail="Unpaywall email not configured"
        )
        # Unpaywall requires email for API access
        # Set UNPAYWALL_EMAIL in .env

    client = UnpaywallClient(email=settings.unpaywall_email)

    try:
        result = await client.get_oa_location(doi)
        # get_oa_location returns Unpaywall response with:
        # - is_oa: boolean
        # - best_oa_location: best available version
        # - oa_locations: all available versions

        if not result:
            raise HTTPException(status_code=404, detail="DOI not found")

        # ─────────────────────────────────────────────────────────────────────
        # Return simplified response
        # ─────────────────────────────────────────────────────────────────────
        return {
            "doi": result.doi,
            "is_oa": result.is_oa,
            "pdf_url": result.get_pdf_url(),
            # get_pdf_url() extracts url_for_pdf from best_oa_location
            "title": result.title,
        }

    finally:
        await client.close()


# =============================================================================
# ENDPOINT: DOWNLOAD ARXIV PDF
# =============================================================================

@router.post("/download/arxiv/{arxiv_id}")
async def download_arxiv_pdf(arxiv_id: str) -> dict:
    """
    Download PDF from arXiv and save locally.

    This endpoint:
    1. Downloads PDF from arXiv servers
    2. Saves to configured pdfs_dir
    3. Returns file info

    Path Parameter:
    ───────────────
    - arxiv_id: arXiv paper ID

    Response:
    ─────────
    ```json
    {
      "arxiv_id": "2301.08422",
      "path": "/app/data/pdfs/2301.08422.pdf",
      "size_bytes": 1234567
    }
    ```

    Storage:
    ────────
    PDFs are saved to: {settings.pdfs_dir}/{arxiv_id}.pdf
    Default: data/pdfs/2301.08422.pdf

    Rate Limiting:
    ──────────────
    arXiv requires 3 seconds between requests. Large downloads may be slow.

    Security:
    ─────────
    - Files saved with sanitized filenames (slashes replaced with underscores)
    - Only downloads from arxiv.org domain
    - No user-controlled paths

    Example:
    ────────
    POST /api/papers/download/arxiv/2301.08422

    Response:
    ```json
    {
      "arxiv_id": "2301.08422",
      "path": "/app/data/pdfs/2301.08422.pdf",
      "size_bytes": 847293
    }
    ```
    """
    settings = get_settings()
    client = ArxivClient()

    try:
        # ─────────────────────────────────────────────────────────────────────
        # Download PDF bytes
        # ─────────────────────────────────────────────────────────────────────
        pdf_content = await client.download_pdf(arxiv_id)
        # download_pdf() returns raw bytes
        # Typical size: 200KB - 5MB

        # ─────────────────────────────────────────────────────────────────────
        # Save to disk
        # ─────────────────────────────────────────────────────────────────────
        # Sanitize filename: replace slashes with underscores
        # Old arXiv IDs have slashes: hep-th/9901001 → hep-th_9901001
        safe_id = arxiv_id.replace("/", "_")
        pdf_path = settings.pdfs_dir / f"{safe_id}.pdf"

        pdf_path.write_bytes(pdf_content)
        # write_bytes() creates file and writes binary content
        # Overwrites if exists

        # ─────────────────────────────────────────────────────────────────────
        # Return file info
        # ─────────────────────────────────────────────────────────────────────
        return {
            "arxiv_id": arxiv_id,
            "path": str(pdf_path),
            # Convert Path to string for JSON serialization
            "size_bytes": len(pdf_content),
        }

    finally:
        await client.close()


# =============================================================================
#                         USAGE NOTES
# =============================================================================
#
# 1. All endpoints are async - they can handle many concurrent requests
#
# 2. API clients are created per-request and closed in finally block
#    This ensures proper resource cleanup even on errors
#
# 3. Rate limits are enforced by the underlying clients:
#    - OpenAlex: 10 req/s (with email)
#    - arXiv: 1 req/3s
#    - Unpaywall: 100K req/day
#
# 4. Error handling:
#    - 400: Bad request (missing config, invalid params)
#    - 404: Resource not found (paper doesn't exist)
#    - 5xx: Server errors (propagated from external APIs)
#
# 5. Response format:
#    - All endpoints return JSON
#    - Paper data normalized to PaperMetadata schema
#    - Consistent field names across APIs
# =============================================================================
