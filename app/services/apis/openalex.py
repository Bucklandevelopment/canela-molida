"""
===============================================================================
                    OPENALEX API CLIENT - DOCUMENTATION
===============================================================================

Module: app/services/apis/openalex.py
Purpose: Async client for OpenAlex, the largest free academic metadata API

===============================================================================
                          WHAT IS OPENALEX?
===============================================================================

OpenAlex is an open-source, comprehensive index of scholarly works:

┌─────────────────────────────────────────────────────────────────────────────┐
│                         OPENALEX OVERVIEW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Coverage:          240+ million scholarly works                           │
│   License:           CC0 (Public Domain - completely free)                  │
│   Update Frequency:  Daily updates                                          │
│   Launched:          January 2022                                           │
│   Operated by:       OurResearch (non-profit)                              │
│   Funding:           Arcadia Fund (open access philanthropy)               │
│                                                                             │
│   Replaces:          Microsoft Academic Graph (deprecated 2021)            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                    OPENALEX DATA ENTITIES
===============================================================================

OpenAlex indexes 5 main entity types, all interconnected:

         ┌─────────────┐
         │   WORKS     │ ◄─── The papers/articles themselves
         │  240M+      │      (title, abstract, citations, etc.)
         └──────┬──────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ AUTHORS │ │ SOURCES │ │CONCEPTS │
│  90M+   │ │  250K+  │ │  65K+   │
│         │ │(journals│ │(topics) │
└────┬────┘ │ repos)  │ └─────────┘
     │      └─────────┘
     ▼
┌──────────────┐
│ INSTITUTIONS │ ◄─── Where authors work
│    100K+     │      (universities, labs, companies)
└──────────────┘

Work Record Structure:
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OPENALEX WORK OBJECT                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   id: "https://openalex.org/W2741809807"    # Unique identifier            │
│   doi: "10.1038/nature12373"                 # If available                 │
│   title: "Attention Is All You Need"         # Normalized title            │
│   display_name: "Attention Is All You Need"  # Display version             │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ ABSTRACT (Inverted Index Format)                                    │   │
│   │                                                                     │   │
│   │ OpenAlex stores abstracts as inverted indexes for compression:      │   │
│   │                                                                     │   │
│   │   abstract_inverted_index: {                                        │   │
│   │     "The": [0],                                                     │   │
│   │     "dominant": [1, 15],                                            │   │
│   │     "sequence": [2, 3],                                             │   │
│   │     "transduction": [4],                                            │   │
│   │     ...                                                             │   │
│   │   }                                                                 │   │
│   │                                                                     │   │
│   │   To reconstruct: Sort positions, join words                        │   │
│   │   Result: "The dominant sequence transduction..."                   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   publication_year: 2017                                                    │
│   cited_by_count: 75000                                                     │
│   is_open_access: true                                                      │
│                                                                             │
│   authorships: [                            # Author list with affiliations │
│     {                                                                       │
│       author: { id: "A123", display_name: "John Doe", orcid: "..." },      │
│       institutions: [{ id: "I456", display_name: "MIT" }],                 │
│       position: "first"                                                     │
│     }                                                                       │
│   ]                                                                         │
│                                                                             │
│   concepts: [                               # Auto-tagged topics            │
│     { id: "C123", display_name: "Machine Learning", score: 0.95, level: 1 }│
│   ]                                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                         RATE LIMITING EXPLAINED
===============================================================================

OpenAlex uses a "polite pool" system for rate limiting:

┌─────────────────────────────────────────────────────────────────────────────┐
│                    POLITE POOL vs ANONYMOUS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   WITH EMAIL (Polite Pool):                                                │
│   ─────────────────────────                                                │
│   - Rate limit: 10 requests/second                                         │
│   - Higher reliability                                                      │
│   - Request: ?mailto=you@example.com                                        │
│                                                                             │
│   WITHOUT EMAIL (Anonymous):                                               │
│   ──────────────────────────                                               │
│   - Rate limit: ~1 request/second (variable)                               │
│   - Subject to throttling during high load                                 │
│   - May experience more 429 errors                                          │
│                                                                             │
│   BULK DATA (Alternative):                                                 │
│   ────────────────────────                                                 │
│   - Monthly S3 snapshots available                                         │
│   - ~300GB compressed for full dataset                                     │
│   - Best for large-scale analysis                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Our Implementation:
- Uses configurable email via settings
- Rate limiting: asyncio.sleep(rate_limit) before each request
- Default: 0.1s delay = 10 req/s max

===============================================================================
                    COMPARISON: OPENALEX vs ALTERNATIVES
===============================================================================

┌───────────────────┬──────────────┬────────────────┬─────────────────────────┐
│ Feature           │ OpenAlex     │ Semantic       │ Crossref                │
│                   │              │ Scholar        │                         │
├───────────────────┼──────────────┼────────────────┼─────────────────────────┤
│ Coverage          │ 240M+ works  │ 200M+ works    │ 140M+ DOIs              │
│ License           │ CC0 (free)   │ Restrictive    │ Public data varies      │
│ Rate Limit        │ 10/s polite  │ 100/5min       │ 50/s polite             │
│ Abstracts         │ Most (inv.)  │ Some           │ Few                     │
│ Citations         │ Yes          │ Yes            │ Reference lists         │
│ AI Concepts       │ Yes (65K)    │ No             │ No                      │
│ Author Disambig.  │ Yes          │ Yes            │ No                      │
│ Institution Data  │ Yes (ROR)    │ Limited        │ No                      │
│ Bulk Download     │ S3 monthly   │ No             │ Partial                 │
│ Best For          │ General      │ AI/ML papers   │ Publisher data          │
└───────────────────┴──────────────┴────────────────┴─────────────────────────┘

Winner: OpenAlex for most use cases (coverage + free + abstracts)

===============================================================================
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import asyncio
# asyncio: Python's async I/O framework
# Used for: Rate limiting via sleep(), concurrent request handling
# Why async? HTTP requests are I/O-bound; async allows thousands of concurrent
# requests on a single thread

from typing import Optional, Any
# Optional: Type hint for values that can be None
# Any: Type hint for dynamic types (API responses before parsing)

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import httpx
# httpx: Modern HTTP client for Python (async-first design)
#
# Why httpx over requests?
# ┌───────────────────┬──────────────────┬───────────────────────────────────┐
# │ Feature           │ httpx            │ requests                          │
# ├───────────────────┼──────────────────┼───────────────────────────────────┤
# │ Async support     │ Native           │ Requires aiohttp                  │
# │ HTTP/2            │ Yes              │ No                                │
# │ Connection pool   │ Built-in         │ Session required                  │
# │ Type hints        │ Full             │ Partial                           │
# │ API compatibility │ requests-like    │ -                                 │
# └───────────────────┴──────────────────┴───────────────────────────────────┘

from tenacity import retry, stop_after_attempt, wait_exponential
# tenacity: Retry library with advanced backoff strategies
#
# Components used:
# - @retry: Decorator to retry failed function calls
# - stop_after_attempt(n): Stop after n tries
# - wait_exponential: Increase wait time exponentially between retries
#
# Why not simple try/except loop?
# - tenacity handles edge cases (async, exceptions, jitter)
# - Cleaner code (decorator vs nested loops)
# - Built-in logging and statistics

# =============================================================================
# LOCAL IMPORTS
# =============================================================================

from app.core.config import get_settings
# get_settings(): Singleton configuration loader
# Provides: openalex_email, openalex_rate_limit

from app.models.api import OpenAlexWork
# OpenAlexWork: Pydantic model for OpenAlex API responses
# Includes: id, doi, title, authorships, concepts, cited_by_count, etc.

from app.models.paper import PaperMetadata, Author
# PaperMetadata: Normalized paper model (source-agnostic)
# Author: Normalized author model with ORCID support


# =============================================================================
# OPENALEX CLIENT CLASS
# =============================================================================

class OpenAlexClient:
    """
    =========================================================================
    OPENALEX ASYNC CLIENT
    =========================================================================

    Asynchronous client for the OpenAlex API, providing methods to search
    and retrieve scholarly work metadata.

    Architecture:
    ┌─────────────────────────────────────────────────────────────────────┐
    │                      OpenAlexClient                                 │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   ┌─────────────────┐    ┌─────────────────┐    ┌───────────────┐  │
    │   │  Public Methods │    │ Private Methods │    │   Attributes  │  │
    │   ├─────────────────┤    ├─────────────────┤    ├───────────────┤  │
    │   │ get_work_by_doi │───►│ _request        │───►│ _client       │  │
    │   │ get_work_by_id  │    │ _params         │    │ email         │  │
    │   │ search_works    │    └─────────────────┘    │ rate_limit    │  │
    │   │ get_works_by_   │                           └───────────────┘  │
    │   │    author       │                                              │
    │   │ work_to_metadata│    Conversion to normalized model            │
    │   └─────────────────┘                                              │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    Usage Examples:
    ──────────────

    # Basic usage (with context manager for cleanup)
    async with OpenAlexClient() as client:
        paper = await client.get_work_by_doi("10.1038/nature12373")
        print(paper.title)

    # Without context manager (manual cleanup required)
    client = OpenAlexClient(email="you@example.com")
    papers = await client.search_works("machine learning", limit=100)
    await client.close()

    # Convert to normalized model
    metadata = client.work_to_metadata(paper)

    Thread Safety:
    ──────────────
    - Each client instance has its own httpx.AsyncClient
    - Instances should NOT be shared across event loops
    - For multi-threaded apps, create one client per thread
    """

    # =========================================================================
    # CLASS CONSTANTS
    # =========================================================================

    BASE_URL = "https://api.openalex.org"
    # OpenAlex API base URL
    # All endpoints are relative to this URL:
    # - /works/{id}     - Get single work
    # - /works          - Search works
    # - /authors/{id}   - Get author info
    # - /sources/{id}   - Get journal/repository info

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self, email: Optional[str] = None):
        """
        Initialize OpenAlex client with optional email for polite pool.

        Args:
            email: Contact email for higher rate limits (polite pool)
                   If not provided, falls back to settings.openalex_email
                   Without email: ~1 req/s
                   With email: 10 req/s

        Technical Details:
        ──────────────────
        The client creates a persistent httpx.AsyncClient with:
        - base_url: Prepended to all request paths
        - timeout: 30 seconds (scientific APIs can be slow)
        - headers: User-Agent for identification

        Why 30s timeout?
        - OpenAlex search queries can take 5-15s for complex filters
        - Default 5s would cause false failures
        - 30s balances reliability vs stuck request detection
        """
        # ─────────────────────────────────────────────────────────────────────
        # Load configuration from centralized settings
        # ─────────────────────────────────────────────────────────────────────
        settings = get_settings()

        # Use provided email or fall back to settings
        self.email = email or settings.openalex_email
        # Email enables "polite pool" with 10x higher rate limit

        # Rate limit delay in seconds (default: 0.1s = 10 req/s max)
        self.rate_limit = settings.openalex_rate_limit

        # ─────────────────────────────────────────────────────────────────────
        # Create async HTTP client
        # ─────────────────────────────────────────────────────────────────────
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            # base_url: All paths in requests are relative to this
            # "/works" becomes "https://api.openalex.org/works"

            timeout=30.0,
            # timeout: Maximum time to wait for response (seconds)
            # httpx uses this for both connect and read timeouts by default

            headers={"User-Agent": "ScientificLibraryRAG/1.0"},
            # User-Agent: Identifies our application to the API
            # Best practice: Include app name and version
            # Helps API providers track usage and contact if issues
        )

    # =========================================================================
    # RESOURCE CLEANUP
    # =========================================================================

    async def close(self) -> None:
        """
        Close HTTP client and release resources.

        Why explicit close?
        ───────────────────
        httpx.AsyncClient maintains a connection pool for efficiency.
        Without closing:
        - Connections may leak
        - File descriptors accumulate
        - EventLoop warnings on shutdown

        Best Practice:
        ──────────────
        Use context manager when possible:

            async with OpenAlexClient() as client:
                ...  # client.close() called automatically

        Or call close() explicitly in finally block:

            client = OpenAlexClient()
            try:
                ...
            finally:
                await client.close()
        """
        await self._client.aclose()
        # aclose(): Async version of close()
        # Closes all connections in the pool
        # Waits for pending requests to complete (with timeout)

    # =========================================================================
    # PARAMETER BUILDING
    # =========================================================================

    def _params(self, **kwargs: Any) -> dict[str, Any]:
        """
        Build request parameters with email for polite pool.

        Args:
            **kwargs: Any request-specific parameters

        Returns:
            Dict with None values filtered out and mailto added

        Example:
        ────────
        >>> client._params(search="quantum", per_page=50, year=None)
        {"search": "quantum", "per_page": 50, "mailto": "user@example.com"}

        Technical Notes:
        ────────────────
        - Filters None values to avoid sending empty params
        - Adds mailto if email configured (polite pool)
        - OpenAlex accepts mailto as query param, not header
        """
        # Filter out None values
        # This allows callers to pass optional params without checking
        params = {k: v for k, v in kwargs.items() if v is not None}

        # Add email for polite pool if configured
        if self.email:
            params["mailto"] = self.email
            # OpenAlex uses "mailto" parameter (not header) for polite pool
            # This identifies the requester for higher rate limits

        return params

    # =========================================================================
    # HTTP REQUEST WITH RETRY
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        # stop_after_attempt(3): Give up after 3 tries
        # Total attempts: 1 (initial) + 2 (retries) = 3

        wait=wait_exponential(multiplier=1, min=1, max=10),
        # wait_exponential: Increase wait time exponentially
        #
        # Formula: wait = multiplier * (2 ** attempt) ± jitter
        #
        # With these settings:
        # - Attempt 1: Failed → wait 1s
        # - Attempt 2: Failed → wait 2s
        # - Attempt 3: Failed → wait 4s (capped at 10s)
        #
        # Why exponential backoff?
        # - Prevents overwhelming recovering servers
        # - Allows transient issues to resolve
        # - Reduces load during outages
    )
    async def _request(self, endpoint: str, params: dict) -> dict[str, Any]:
        """
        Make API request with retry logic and rate limiting.

        Args:
            endpoint: API endpoint path (e.g., "/works")
            params: Query parameters

        Returns:
            Parsed JSON response as dict

        Raises:
            httpx.HTTPStatusError: For 4xx/5xx responses after retries
            httpx.TimeoutException: If request times out

        Technical Flow:
        ───────────────

        1. Rate limit (asyncio.sleep)
           ↓
        2. Send HTTP GET request
           ↓
        3. Check status code (raise_for_status)
           ↓
        4. Parse JSON response
           ↓
        5. Return dict

        If 3 fails → tenacity retries with exponential backoff
        """
        # ─────────────────────────────────────────────────────────────────────
        # Rate limiting
        # ─────────────────────────────────────────────────────────────────────
        await asyncio.sleep(self.rate_limit)
        # asyncio.sleep(): Non-blocking sleep
        # Allows other coroutines to run during the wait
        #
        # This is CLIENT-SIDE rate limiting:
        # - Proactive: Prevents hitting server limits
        # - Predictable: Smooth request distribution
        # - Polite: Respects API provider resources

        # ─────────────────────────────────────────────────────────────────────
        # Make HTTP request
        # ─────────────────────────────────────────────────────────────────────
        response = await self._client.get(endpoint, params=params)
        # _client.get(): Async HTTP GET request
        # - endpoint: Combined with base_url
        # - params: Automatically URL-encoded as query string

        # ─────────────────────────────────────────────────────────────────────
        # Error handling
        # ─────────────────────────────────────────────────────────────────────
        response.raise_for_status()
        # raise_for_status(): Raises HTTPStatusError for 4xx/5xx
        #
        # Common OpenAlex errors:
        # - 404: DOI/ID not found
        # - 429: Rate limit exceeded (retry will help)
        # - 500: Server error (retry may help)
        # - 503: Service unavailable (retry will help)

        # ─────────────────────────────────────────────────────────────────────
        # Parse and return JSON
        # ─────────────────────────────────────────────────────────────────────
        return response.json()
        # .json(): Parse response body as JSON
        # Returns dict for objects, list for arrays
        # Raises JSONDecodeError if invalid JSON

    # =========================================================================
    # PUBLIC API: GET WORK BY DOI
    # =========================================================================

    async def get_work_by_doi(self, doi: str) -> Optional[OpenAlexWork]:
        """
        Get paper by DOI (Digital Object Identifier).

        Args:
            doi: DOI string (with or without URL prefix)
                 Examples: "10.1038/nature12373"
                          "https://doi.org/10.1038/nature12373"

        Returns:
            OpenAlexWork if found, None if DOI not in database

        Example:
        ────────
        paper = await client.get_work_by_doi("10.1038/nature12373")
        if paper:
            print(f"{paper.title} has {paper.cited_by_count} citations")

        DOI Format:
        ───────────
        DOI (Digital Object Identifier) is a permanent identifier for documents.

        Format: prefix/suffix
        - Prefix: Registrant code (e.g., 10.1038 = Nature Publishing)
        - Suffix: Item identifier (assigned by publisher)

        Common prefixes:
        - 10.1038  = Nature
        - 10.1126  = Science (AAAS)
        - 10.1016  = Elsevier
        - 10.1371  = PLOS
        - 10.1109  = IEEE
        - 10.48550 = arXiv

        OpenAlex DOI Endpoint:
        ──────────────────────
        /works/doi:{doi} - Direct lookup by DOI
        Much faster than search query
        """
        try:
            # ─────────────────────────────────────────────────────────────────
            # Call OpenAlex DOI endpoint
            # ─────────────────────────────────────────────────────────────────
            data = await self._request(
                f"/works/doi:{doi}",
                # OpenAlex DOI lookup syntax: /works/doi:10.1038/...
                # No need to URL-encode the DOI (httpx handles it)
                self._params(),
            )

            # ─────────────────────────────────────────────────────────────────
            # Parse response into Pydantic model
            # ─────────────────────────────────────────────────────────────────
            return OpenAlexWork(**data)
            # OpenAlexWork(**data): Pydantic model instantiation
            # - Validates response against expected schema
            # - Provides type hints for IDE autocomplete
            # - Handles missing optional fields

        except httpx.HTTPStatusError as e:
            # ─────────────────────────────────────────────────────────────────
            # Handle 404: DOI not found
            # ─────────────────────────────────────────────────────────────────
            if e.response.status_code == 404:
                return None
                # 404 is expected for unknown DOIs
                # Return None instead of raising exception
            raise
            # Re-raise other HTTP errors (500, 503, etc.)
            # tenacity will retry if configured

    # =========================================================================
    # PUBLIC API: GET WORK BY OPENALEX ID
    # =========================================================================

    async def get_work_by_id(self, openalex_id: str) -> Optional[OpenAlexWork]:
        """
        Get paper by OpenAlex ID.

        Args:
            openalex_id: OpenAlex work ID (e.g., "W2741809807")
                        Can also use full URL form

        Returns:
            OpenAlexWork if found

        OpenAlex ID Format:
        ───────────────────
        OpenAlex assigns unique IDs to all entities:

        - Works:        W + number  (W2741809807)
        - Authors:      A + number  (A5023888391)
        - Sources:      S + number  (S137773608)
        - Institutions: I + number  (I27837315)
        - Concepts:     C + number  (C41008148)

        The ID is also available as a URL:
        https://openalex.org/W2741809807

        Why use OpenAlex ID vs DOI?
        ───────────────────────────
        - Works without DOI: ~15% of works lack DOIs
        - Preprints: May have arXiv ID but no DOI
        - Internal references: Store OpenAlex IDs for consistency
        """
        try:
            data = await self._request(
                f"/works/{openalex_id}",
                # Direct ID lookup: /works/W2741809807
                self._params(),
            )
            return OpenAlexWork(**data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # =========================================================================
    # PUBLIC API: SEARCH WORKS
    # =========================================================================

    async def search_works(
        self,
        query: str,
        limit: int = 25,
        page: int = 1,
        filter_oa: bool = False,
        filter_year: Optional[int] = None,
        filter_year_range: Optional[tuple[int, int]] = None,
        sort_by: str = "relevance_score",
    ) -> list[OpenAlexWork]:
        """
        Search for papers matching a query.

        Args:
            query: Search query (searches title, abstract, full text)
            limit: Results per page (max 200)
            page: Page number (1-indexed)
            filter_oa: Only return Open Access papers
            filter_year: Exact publication year filter
            filter_year_range: (min_year, max_year) tuple
            sort_by: Sort field

        Returns:
            List of matching works

        Search Syntax:
        ──────────────
        OpenAlex uses simple keyword search by default.

        Examples:
        - "machine learning"  → Both words anywhere
        - "machine learning"  → Exact phrase (use quotes)

        Sort Options:
        ─────────────
        - relevance_score: Best match first (default)
        - cited_by_count: Most cited first
        - publication_date: Newest first
        - publication_date:asc: Oldest first

        Filter Syntax:
        ──────────────
        OpenAlex uses a powerful filter system:

        - is_oa:true              → Only open access
        - publication_year:2023   → Exact year
        - publication_year:2020-  → 2020 and later
        - publication_year:-2020  → 2020 and earlier
        - publication_year:2020-2023 → Range

        Combine with comma (AND logic):
        - is_oa:true,publication_year:2023

        Pagination:
        ───────────
        - page=1, per_page=25 → Results 1-25
        - page=2, per_page=25 → Results 26-50
        - max per_page: 200

        Example:
        ────────
        # Get 100 OA papers on transformers from 2023
        papers = await client.search_works(
            "transformer neural network",
            limit=100,
            filter_oa=True,
            filter_year=2023,
            sort_by="cited_by_count"
        )
        """
        # ─────────────────────────────────────────────────────────────────────
        # Build filter string
        # ─────────────────────────────────────────────────────────────────────
        filters = []

        if filter_oa:
            filters.append("is_oa:true")
            # Only return works with open access versions

        if filter_year:
            filters.append(f"publication_year:{filter_year}")
            # Exact year match

        if filter_year_range:
            filters.append(
                f"publication_year:{filter_year_range[0]}-{filter_year_range[1]}"
            )
            # Year range: 2020-2023

        # ─────────────────────────────────────────────────────────────────────
        # Build request parameters
        # ─────────────────────────────────────────────────────────────────────
        params = self._params(
            search=query,
            # search: Full-text search query

            per_page=min(limit, 200),
            # per_page: Results per page
            # Capped at 200 (OpenAlex maximum)

            page=page,
            # page: Pagination offset (1-indexed)

            sort=sort_by,
            # sort: Sort field and direction
        )

        if filters:
            params["filter"] = ",".join(filters)
            # filter: Comma-separated filter expressions
            # Comma = AND logic between filters

        # ─────────────────────────────────────────────────────────────────────
        # Execute search
        # ─────────────────────────────────────────────────────────────────────
        data = await self._request("/works", params)

        # ─────────────────────────────────────────────────────────────────────
        # Parse results
        # ─────────────────────────────────────────────────────────────────────
        results = data.get("results", [])
        # OpenAlex wraps results in: {"results": [...], "meta": {...}}

        return [OpenAlexWork(**w) for w in results]
        # Convert each result dict to Pydantic model

    # =========================================================================
    # PUBLIC API: GET WORKS BY AUTHOR
    # =========================================================================

    async def get_works_by_author(
        self,
        author_id: str,
        limit: int = 100,
    ) -> list[OpenAlexWork]:
        """
        Get papers by author OpenAlex ID.

        Args:
            author_id: OpenAlex author ID (e.g., "A5023888391")
                      Can also use ORCID: "https://orcid.org/0000-0002-..."

        Returns:
            List of author's works, sorted by publication date (newest first)

        Example:
        ────────
        # Get papers by Yoshua Bengio
        papers = await client.get_works_by_author("A5023888391")
        for paper in papers[:10]:
            print(f"{paper.publication_year}: {paper.title}")

        Finding Author IDs:
        ───────────────────
        1. Search by name: GET /authors?search=yoshua%20bengio
        2. Use ORCID directly: A5023888391 → https://orcid.org/0000-0002-...
        3. Extract from work: work.authorships[0].author.id

        Note on Author Disambiguation:
        ──────────────────────────────
        OpenAlex uses ML to disambiguate authors with same name.
        Based on:
        - Co-author patterns
        - Institution affiliations
        - Citation networks
        - Topic similarity
        """
        params = self._params(
            filter=f"author.id:{author_id}",
            # Filter works by author ID

            per_page=min(limit, 200),
            # Limit results (max 200 per page)

            sort="publication_date:desc",
            # Sort by date, newest first
        )

        data = await self._request("/works", params)
        return [OpenAlexWork(**w) for w in data.get("results", [])]

    # =========================================================================
    # DATA CONVERSION: OPENALEX → NORMALIZED MODEL
    # =========================================================================

    def work_to_metadata(self, work: OpenAlexWork) -> PaperMetadata:
        """
        Convert OpenAlex work to normalized PaperMetadata model.

        Args:
            work: OpenAlex work object

        Returns:
            PaperMetadata with source-agnostic fields

        Why Convert?
        ────────────
        Different APIs return different schemas:
        - OpenAlex: authorships[].author.display_name
        - arXiv: authors[] (just names)
        - Crossref: author[].given, author[].family

        PaperMetadata provides a unified interface:
        - Same field names across all sources
        - Consistent types (dates, lists, optionals)
        - Easy to store/index/display

        Conversion Details:
        ───────────────────

        1. Authors: Extract from nested authorships structure
           - Name from author.display_name
           - ORCID from author.orcid (if available)
           - Affiliation from first institution

        2. Abstract: Reconstruct from inverted index
           - OpenAlex stores abstracts as {word: [positions]}
           - Use work.get_abstract() to reconstruct

        3. DOI: Strip URL prefix if present
           - "https://doi.org/10.1038/..." → "10.1038/..."

        4. Concepts: Filter to level ≤ 2 (top-level topics)
           - Level 0: Very broad (Science)
           - Level 1: Broad (Physics)
           - Level 2: Specific (Quantum Computing)
        """
        # ─────────────────────────────────────────────────────────────────────
        # Extract authors from nested authorships structure
        # ─────────────────────────────────────────────────────────────────────
        authors = []
        for authorship in work.authorships:
            # authorship structure:
            # {
            #   "author": {"id": "A123", "display_name": "John Doe", "orcid": "..."},
            #   "institutions": [{"id": "I456", "display_name": "MIT"}],
            #   "author_position": "first"
            # }

            author_data = authorship.get("author", {})
            institutions = authorship.get("institutions", [])

            # Get first institution as affiliation
            affiliation = institutions[0].get("display_name") if institutions else None

            authors.append(
                Author(
                    name=author_data.get("display_name", "Unknown"),
                    # display_name: Formatted name (e.g., "John Doe")

                    orcid=author_data.get("orcid"),
                    # orcid: ORCID identifier (if available)
                    # Format: "https://orcid.org/0000-0002-..."

                    affiliation=affiliation,
                    # affiliation: First listed institution
                )
            )

        # ─────────────────────────────────────────────────────────────────────
        # Extract Open Access information
        # ─────────────────────────────────────────────────────────────────────
        oa_info = work.open_access or {}
        # open_access: {"is_oa": true, "oa_status": "gold", "oa_url": "..."}

        best_oa = work.best_oa_location or {}
        # best_oa_location: Best available OA version
        # Includes pdf_url if PDF directly available

        # ─────────────────────────────────────────────────────────────────────
        # Extract external identifiers
        # ─────────────────────────────────────────────────────────────────────
        ids = work.ids or {}
        # ids: {"doi": "...", "pmid": "...", "pmcid": "...", "openalex": "..."}

        # ─────────────────────────────────────────────────────────────────────
        # Extract and filter concepts (topics)
        # ─────────────────────────────────────────────────────────────────────
        concepts = [
            c.get("display_name", "")
            for c in work.concepts
            if c.get("level", 0) <= 2
            # Filter to level 0-2 (avoid overly specific concepts)
            # Level 3+: Very specific (e.g., "BERT", "GPT-2")
        ]

        # ─────────────────────────────────────────────────────────────────────
        # Build normalized PaperMetadata
        # ─────────────────────────────────────────────────────────────────────
        return PaperMetadata(
            doi=work.doi.replace("https://doi.org/", "") if work.doi else None,
            # Strip URL prefix from DOI

            openalex_id=work.id,
            # Keep OpenAlex ID for future lookups

            pmid=ids.get("pmid"),
            # PubMed ID (for biomedical papers)

            pmcid=ids.get("pmcid"),
            # PubMed Central ID (for free full-text)

            title=work.display_name or work.title or "Untitled",
            # Prefer display_name (better formatting)

            abstract=work.get_abstract(),
            # Reconstruct from inverted index

            authors=authors,
            # Normalized author list

            year=work.publication_year,
            # Publication year

            is_open_access=oa_info.get("is_oa", False),
            # Boolean: Is any OA version available?

            oa_url=oa_info.get("oa_url"),
            # URL to OA version (landing page)

            pdf_url=best_oa.get("pdf_url"),
            # Direct PDF URL (if available)

            cited_by_count=work.cited_by_count,
            # Citation count

            concepts=concepts,
            # Topic labels

            source_api="openalex",
            # Track data source for debugging/analytics
        )


# =============================================================================
#                          USAGE EXAMPLES
# =============================================================================
#
# Example 1: Basic DOI lookup
# ───────────────────────────
# async def main():
#     client = OpenAlexClient(email="your@email.com")
#     try:
#         paper = await client.get_work_by_doi("10.1038/nature12373")
#         if paper:
#             print(f"Title: {paper.title}")
#             print(f"Citations: {paper.cited_by_count}")
#             print(f"Abstract: {paper.get_abstract()[:200]}...")
#     finally:
#         await client.close()
#
# Example 2: Search with filters
# ──────────────────────────────
# async def search_oa_papers():
#     async with OpenAlexClient() as client:
#         papers = await client.search_works(
#             "CRISPR gene editing",
#             limit=50,
#             filter_oa=True,
#             filter_year_range=(2020, 2024),
#             sort_by="cited_by_count"
#         )
#         for paper in papers:
#             meta = client.work_to_metadata(paper)
#             print(f"{meta.year}: {meta.title} ({meta.cited_by_count} cites)")
#
# Example 3: Build paper corpus by author
# ───────────────────────────────────────
# async def get_author_papers(author_id: str):
#     client = OpenAlexClient()
#     papers = await client.get_works_by_author(author_id, limit=200)
#     return [client.work_to_metadata(p) for p in papers]
# =============================================================================
