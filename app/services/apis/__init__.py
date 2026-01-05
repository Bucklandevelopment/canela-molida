"""
===============================================================================
                    SCIENTIFIC APIS MODULE - DOCUMENTATION
===============================================================================

Module: app/services/apis/__init__.py
Purpose: Central registry and export of all scientific API clients

===============================================================================
                         ECOSYSTEM OF SCIENTIFIC APIS
===============================================================================

The scientific publishing ecosystem consists of multiple data sources, each
with distinct characteristics, coverage, and access patterns:

┌─────────────────────────────────────────────────────────────────────────────┐
│                    SCIENTIFIC DATA SOURCES TAXONOMY                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    PRIMARY SOURCES (Metadata)                       │   │
│   │                                                                     │   │
│   │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │   │
│   │   │   OpenAlex    │  │   Crossref    │  │  Semantic     │          │   │
│   │   │   240M+ docs  │  │   140M+ DOIs  │  │  Scholar      │          │   │
│   │   │   CC0 license │  │   Publisher   │  │   200M+ docs  │          │   │
│   │   │   Best for    │  │   official    │  │   AI/ML       │          │   │
│   │   │   bulk data   │  │   source      │  │   focused     │          │   │
│   │   └───────────────┘  └───────────────┘  └───────────────┘          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                   PREPRINT SERVERS (Full Text)                      │   │
│   │                                                                     │   │
│   │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │   │
│   │   │    arXiv      │  │   bioRxiv     │  │   medRxiv     │          │   │
│   │   │   2.5M+ docs  │  │   Preprint    │  │   Preprint    │          │   │
│   │   │   Physics/CS  │  │   Biology     │  │   Medicine    │          │   │
│   │   │   /Math/etc   │  │               │  │               │          │   │
│   │   └───────────────┘  └───────────────┘  └───────────────┘          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     OPEN ACCESS DISCOVERY                           │   │
│   │                                                                     │   │
│   │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │   │
│   │   │  Unpaywall    │  │   CORE        │  │   BASE        │          │   │
│   │   │   OA lookup   │  │   Open repo   │  │   Academic    │          │   │
│   │   │   by DOI      │  │   aggregator  │  │   aggregator  │          │   │
│   │   └───────────────┘  └───────────────┘  └───────────────┘          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    SPECIALIZED SOURCES                              │   │
│   │                                                                     │   │
│   │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐          │   │
│   │   │    PubMed     │  │  Nobel Prize  │  │   Wikidata    │          │   │
│   │   │   36M+ docs   │  │   Official    │  │   Universal   │          │   │
│   │   │   Biomedical  │  │   Prize API   │  │   SPARQL      │          │   │
│   │   └───────────────┘  └───────────────┘  └───────────────┘          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                      API COMPARISON TABLE - RATE LIMITS
===============================================================================

┌────────────────┬──────────────┬─────────────────┬───────────────────────────┐
│ API            │ Rate Limit   │ Auth Required   │ Notes                     │
├────────────────┼──────────────┼─────────────────┼───────────────────────────┤
│ OpenAlex       │ 10 req/s     │ Email (polite)  │ Without email: 1 req/s    │
│ arXiv          │ 1 req/3s     │ No              │ Strict, will block        │
│ Unpaywall      │ 100K/day     │ Email           │ ~1.15 req/s sustained     │
│ Crossref       │ 50 req/s     │ Email (polite)  │ Without email: variable   │
│ Semantic Sch.  │ 100 req/5min │ API Key (opt)   │ Stricter for heavy use    │
│ PubMed         │ 3 req/s      │ API Key (opt)   │ With key: 10 req/s        │
│ Nobel Prize    │ No limit     │ No              │ Small dataset (~1000)     │
│ Wikidata       │ ~5 req/s     │ No              │ Complex queries slower    │
└────────────────┴──────────────┴─────────────────┴───────────────────────────┘

===============================================================================
                    IMPLEMENTATION PATTERNS USED
===============================================================================

All clients in this module follow these design patterns:

1. ASYNC/AWAIT PATTERN
   ────────────────────
   All clients are async-first using httpx.AsyncClient

   Why async?
   - Scientific APIs have high latency (100-500ms typical)
   - Async allows concurrent requests without blocking
   - Single event loop can handle thousands of pending requests

   Example:
   ```python
   # Sequential (slow): 10 requests × 300ms = 3 seconds
   for doi in dois:
       paper = await client.get_work_by_doi(doi)

   # Concurrent (fast): 10 requests in ~300ms
   papers = await asyncio.gather(*[
       client.get_work_by_doi(doi) for doi in dois
   ])
   ```

2. RETRY WITH EXPONENTIAL BACKOFF
   ────────────────────────────────
   Using tenacity library for automatic retries

   Pattern:
   ```python
   @retry(
       stop=stop_after_attempt(3),           # Max 3 attempts
       wait=wait_exponential(                 # Exponential backoff
           multiplier=1,                      # Base delay
           min=1,                             # Min 1 second
           max=10,                            # Max 10 seconds
       ),
   )
   async def _request(self, ...):
       ...
   ```

   Backoff sequence: 1s → 2s → 4s (capped at 10s)

   Why exponential backoff?
   - Prevents thundering herd on API recovery
   - Gives time for transient failures to resolve
   - Respects API provider infrastructure

3. RATE LIMITING
   ───────────────
   Implemented via asyncio.sleep before each request

   Why client-side rate limiting?
   - Prevents 429 errors (Too Many Requests)
   - More predictable than handling server rejections
   - Smoother request distribution

4. PYDANTIC MODEL CONVERSION
   ──────────────────────────
   Each client converts API responses to our internal models

   Pattern: work_to_metadata() or entry_to_metadata()

   Why normalize?
   - Consistent interface for downstream processing
   - Handles API quirks (e.g., OpenAlex inverted abstracts)
   - Single PaperMetadata model for all sources

===============================================================================
                         WHICH API TO USE WHEN?
===============================================================================

Decision tree for paper discovery:

                    ┌──────────────────────┐
                    │    Have DOI?         │
                    └──────────┬───────────┘
                               │
              ┌────────────────┴────────────────┐
              │ Yes                             │ No
              ▼                                 ▼
    ┌─────────────────────┐        ┌─────────────────────────┐
    │ Use OpenAlex first  │        │  Searching by keyword?  │
    │ (fastest, most data)│        └───────────┬─────────────┘
    └─────────┬───────────┘                    │
              │                   ┌────────────┴────────────┐
              │                   │ Yes                     │ No
              ▼                   ▼                         ▼
    ┌─────────────────────┐   ┌───────────────┐   ┌───────────────┐
    │ Need OA PDF?        │   │ OpenAlex for  │   │ Prize data?   │
    │ Try Unpaywall       │   │ broad search  │   │               │
    └─────────────────────┘   │               │   │ Nobel: yes    │
                              │ arXiv for     │   │ Other: Wiki   │
                              │ preprints     │   │ data SPARQL   │
                              └───────────────┘   └───────────────┘

===============================================================================
                         EXPORTED CLIENTS
===============================================================================
"""

# =============================================================================
# IMPORTS - Each client handles a specific scientific data source
# =============================================================================

from app.services.apis.openalex import OpenAlexClient
# OpenAlex: 240M+ documents, CC0 license, best cost/benefit
# - Metadata: title, abstract, authors, citations, concepts
# - 10 req/s with email, bulk download available
# - Replaced Microsoft Academic Graph (MAG)

from app.services.apis.arxiv import ArxivClient
# arXiv: 2.5M+ preprints, direct PDF access
# - Full text available, not just metadata
# - Categories: physics, math, CS, quantitative biology, etc.
# - 1 req/3s rate limit (strict)

from app.services.apis.unpaywall import UnpaywallClient
# Unpaywall: Open Access discovery by DOI
# - Finds legal OA versions of papers
# - Essential for PDF retrieval when only DOI is known
# - 100K requests/day with email

from app.services.apis.nobel import NobelClient
# Nobel Prize: Official API for Nobel laureates
# - Complete data since 1901
# - 6 categories: Physics, Chemistry, Medicine, Literature, Peace, Economics
# - No rate limit (small dataset)

from app.services.apis.wikidata import WikidataClient
# Wikidata: Universal SPARQL for all scientific prizes
# - Fields Medal, Turing Award, Abel Prize, etc.
# - Also useful for scientist disambiguation
# - SPARQL queries (flexible but complex)

# =============================================================================
# PUBLIC API - What this module exports
# =============================================================================

__all__ = [
    # Primary discovery APIs
    "OpenAlexClient",   # Start here for most paper lookups
    "ArxivClient",      # For preprints and direct PDF

    # Open Access discovery
    "UnpaywallClient",  # Find legal OA PDFs by DOI

    # Prize and recognition data
    "NobelClient",      # Official Nobel Prize data
    "WikidataClient",   # Other scientific prizes via SPARQL
]

# =============================================================================
#                          USAGE EXAMPLES
# =============================================================================
#
# Example 1: Basic paper lookup
# ─────────────────────────────
# ```python
# from app.services.apis import OpenAlexClient
#
# async with OpenAlexClient() as client:
#     paper = await client.get_work_by_doi("10.1038/nature12373")
#     print(paper.title, paper.cited_by_count)
# ```
#
# Example 2: Search and download
# ──────────────────────────────
# ```python
# from app.services.apis import ArxivClient
#
# async with ArxivClient() as client:
#     papers = await client.search("quantum computing", max_results=10)
#     for paper in papers:
#         pdf = await client.download_pdf(paper.arxiv_id)
# ```
#
# Example 3: Find OA version
# ──────────────────────────
# ```python
# from app.services.apis import UnpaywallClient
#
# async with UnpaywallClient() as client:
#     result = await client.get_oa_location("10.1126/science.1234567")
#     if result and result.is_oa:
#         pdf_url = result.get_pdf_url()
# ```
#
# Example 4: Prize winners
# ────────────────────────
# ```python
# from app.services.apis import WikidataClient
#
# async with WikidataClient() as client:
#     fields_medalists = await client.get_fields_medal_winners(year=2022)
#     turing_winners = await client.get_turing_award_winners()
# ```
# =============================================================================
