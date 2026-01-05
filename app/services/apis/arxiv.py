"""
===============================================================================
                        ARXIV API CLIENT - DOCUMENTATION
===============================================================================

Module: app/services/apis/arxiv.py
Purpose: Async client for arXiv, the premier preprint server for sciences

===============================================================================
                            WHAT IS ARXIV?
===============================================================================

arXiv (pronounced "archive") is the pioneering open-access preprint repository:

┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARXIV OVERVIEW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Founded:        1991 (originally at LANL, now Cornell)                    │
│   Coverage:       2.5+ million papers                                       │
│   Growth:         ~20,000 new submissions/month                             │
│   License:        Authors retain copyright; most CC-BY or similar           │
│   Operated by:    Cornell University Library                                │
│   Funded by:      Member institutions + Simons Foundation                   │
│                                                                             │
│   Unique Value:   FREE FULL-TEXT PDFs for all papers                       │
│                   (unlike most metadata-only APIs)                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                         ARXIV SUBJECT CATEGORIES
===============================================================================

arXiv organizes papers into major categories (archives) and subcategories:

┌──────────────────────────────────────────────────────────────────────────────┐
│                         ARXIV CATEGORY HIERARCHY                            │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   PHYSICS (Main archive)                                                     │
│   ├── astro-ph     Astrophysics                                             │
│   │   ├── astro-ph.CO  Cosmology and Nongalactic Astrophysics              │
│   │   ├── astro-ph.EP  Earth and Planetary Astrophysics                    │
│   │   ├── astro-ph.GA  Astrophysics of Galaxies                            │
│   │   ├── astro-ph.HE  High Energy Astrophysical Phenomena                 │
│   │   ├── astro-ph.IM  Instrumentation and Methods                         │
│   │   └── astro-ph.SR  Solar and Stellar Astrophysics                      │
│   ├── cond-mat     Condensed Matter                                         │
│   ├── gr-qc        General Relativity and Quantum Cosmology                │
│   ├── hep-ex       High Energy Physics - Experiment                         │
│   ├── hep-lat      High Energy Physics - Lattice                            │
│   ├── hep-ph       High Energy Physics - Phenomenology                      │
│   ├── hep-th       High Energy Physics - Theory                             │
│   ├── math-ph      Mathematical Physics                                      │
│   ├── nucl-ex      Nuclear Experiment                                        │
│   ├── nucl-th      Nuclear Theory                                            │
│   ├── physics      Physics (general)                                         │
│   ├── quant-ph     Quantum Physics                                           │
│   └── ...                                                                    │
│                                                                              │
│   MATHEMATICS (math)                                                         │
│   ├── math.AG      Algebraic Geometry                                       │
│   ├── math.AT      Algebraic Topology                                       │
│   ├── math.CO      Combinatorics                                             │
│   ├── math.NT      Number Theory                                             │
│   └── ... (32 subcategories)                                                │
│                                                                              │
│   COMPUTER SCIENCE (cs)                                                      │
│   ├── cs.AI        Artificial Intelligence                                  │
│   ├── cs.CL        Computation and Language (NLP)                           │
│   ├── cs.CV        Computer Vision                                           │
│   ├── cs.LG        Machine Learning                                          │
│   ├── cs.NE        Neural and Evolutionary Computing                        │
│   └── ... (40 subcategories)                                                │
│                                                                              │
│   OTHER ARCHIVES                                                             │
│   ├── q-bio        Quantitative Biology                                     │
│   ├── q-fin        Quantitative Finance                                     │
│   ├── stat         Statistics                                                │
│   └── eess         Electrical Engineering and Systems Science              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                          ARXIV ID FORMAT
===============================================================================

arXiv IDs have evolved over time:

┌─────────────────────────────────────────────────────────────────────────────┐
│                         ARXIV ID FORMATS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   OLD FORMAT (before April 2007):                                           │
│   ───────────────────────────────                                           │
│   archive/YYMMNNN   Example: hep-th/9901001                                │
│   │      │ │└──────── Sequence number within month                         │
│   │      │ └───────── Month (01-12)                                        │
│   │      └─────────── Year (2-digit)                                       │
│   └────────────────── Archive name                                         │
│                                                                             │
│   NEW FORMAT (April 2007 onwards):                                          │
│   ────────────────────────────────                                          │
│   YYMM.NNNNN        Example: 2301.08422                                    │
│   │  │ └────────────── Sequence number (5 digits since 2015)               │
│   │  └──────────────── Month (01-12)                                       │
│   └─────────────────── Year (2-digit)                                      │
│                                                                             │
│   VERSION SUFFIX:                                                           │
│   ───────────────                                                           │
│   Papers can have multiple versions: 2301.08422v1, 2301.08422v2            │
│   Latest version is default if suffix omitted                              │
│                                                                             │
│   URLS:                                                                     │
│   ─────                                                                     │
│   Abstract page: https://arxiv.org/abs/2301.08422                          │
│   PDF:           https://arxiv.org/pdf/2301.08422.pdf                      │
│   Source (TeX):  https://arxiv.org/e-print/2301.08422                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                         RATE LIMITING - CRITICAL
===============================================================================

arXiv has STRICT rate limits that WILL result in temporary bans:

┌─────────────────────────────────────────────────────────────────────────────┐
│                      ARXIV RATE LIMITING POLICY                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   LIMIT:    1 request per 3 seconds (0.33 req/s)                           │
│                                                                             │
│   VIOLATIONS:                                                               │
│   - First offense: 5-minute ban                                             │
│   - Repeat offenses: Hours to days ban                                      │
│   - Severe abuse: Permanent IP ban                                          │
│                                                                             │
│   ALTERNATIVES FOR BULK DATA:                                               │
│   ───────────────────────────                                               │
│   - OAI-PMH: For metadata harvesting (incremental updates)                 │
│   - S3 Bulk: Full dataset (~9.2 TB, requires AWS costs)                    │
│   - Kaggle: Monthly metadata snapshots (~500 MB)                           │
│                                                                             │
│   OUR IMPLEMENTATION:                                                       │
│   ───────────────────                                                       │
│   - asyncio.sleep(3.0) before each request                                 │
│   - Configurable via settings.arxiv_rate_limit                             │
│   - Retry with exponential backoff (3s → 6s → 12s)                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                         ARXIV API RESPONSE FORMAT
===============================================================================

arXiv uses Atom XML format (not JSON):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.08422v1</id>
    <title>Attention Is All You Need</title>
    <summary>The dominant sequence transduction models...</summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <published>2017-06-12T17:57:34Z</published>
    <updated>2017-12-06T18:16:28Z</updated>
    <arxiv:primary_category term="cs.CL"/>
    <category term="cs.CL"/>
    <category term="cs.LG"/>
    <arxiv:comment>15 pages, 5 figures</arxiv:comment>
    <arxiv:journal_ref>NIPS 2017</arxiv:journal_ref>
    <arxiv:doi>10.48550/arXiv.1706.03762</arxiv:doi>
  </entry>
</feed>
```

Why XML instead of JSON?
- arXiv API dates from 2007 (before JSON APIs became standard)
- Atom is a standard syndication format (like RSS)
- Maintains backwards compatibility

===============================================================================
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import asyncio
# asyncio: Python's async I/O framework
# Used for: Rate limiting via sleep(), concurrent request handling

import re
# re: Regular expressions module
# Used for: Cleaning arXiv IDs (removing version suffixes)

import xml.etree.ElementTree as ET
# ElementTree: XML parsing library (built into Python)
# Used for: Parsing arXiv Atom XML responses
#
# Why ElementTree vs lxml?
# - ElementTree: Built-in, no dependencies, fast enough for arXiv responses
# - lxml: Faster, but requires C library compilation
# For API responses (small XML), ElementTree is sufficient

from datetime import datetime
# datetime: Date/time handling
# Used for: Parsing ISO 8601 timestamps from arXiv

from typing import Optional
# Optional: Type hint for values that can be None

from urllib.parse import urlencode
# urlencode: URL query string encoding
# Used for: Building arXiv API query URLs
# Example: {"search_query": "quantum"} → "search_query=quantum"

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import httpx
# httpx: Modern async HTTP client
# See openalex.py for detailed comparison with requests

from tenacity import retry, stop_after_attempt, wait_exponential
# tenacity: Retry library with exponential backoff
# See openalex.py for detailed explanation

# =============================================================================
# LOCAL IMPORTS
# =============================================================================

from app.core.config import get_settings
# get_settings(): Singleton configuration loader
# Provides: arxiv_rate_limit (default: 3.0 seconds)

from app.models.api import ArxivEntry
# ArxivEntry: Pydantic model for arXiv API responses
# Fields: arxiv_id, title, summary, authors, published, categories, etc.

from app.models.paper import PaperMetadata, Author
# PaperMetadata: Normalized paper model (source-agnostic)
# Author: Normalized author model

# =============================================================================
# XML NAMESPACE CONSTANTS
# =============================================================================

ATOM_NS = "{http://www.w3.org/2005/Atom}"
# ATOM_NS: Atom syndication format namespace
# Used for: Standard elements like <title>, <author>, <published>
#
# In ElementTree, namespace-qualified tags are written as:
# "{namespace_uri}tag_name"
#
# So <title> in Atom namespace becomes:
# "{http://www.w3.org/2005/Atom}title"

ARXIV_NS = "{http://arxiv.org/schemas/atom}"
# ARXIV_NS: arXiv-specific extension namespace
# Used for: arXiv-specific elements like <arxiv:comment>, <arxiv:doi>
#
# Example:
# <arxiv:primary_category term="cs.AI"/>
# Accessed as: element.find(f"{ARXIV_NS}primary_category")


# =============================================================================
# ARXIV CLIENT CLASS
# =============================================================================

class ArxivClient:
    """
    =========================================================================
    ARXIV ASYNC CLIENT
    =========================================================================

    Asynchronous client for the arXiv API, providing methods to search
    papers and download PDFs directly.

    Architecture:
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        ArxivClient                                  │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   ┌─────────────────┐    ┌─────────────────┐    ┌───────────────┐  │
    │   │  Public Methods │    │ Private Methods │    │   Attributes  │  │
    │   ├─────────────────┤    ├─────────────────┤    ├───────────────┤  │
    │   │ search          │───►│ _request        │───►│ _client       │  │
    │   │ search_by_cat   │    │ _parse_entry    │    │ rate_limit    │  │
    │   │ get_by_id       │    └─────────────────┘    └───────────────┘  │
    │   │ get_by_ids      │                                              │
    │   │ download_pdf    │    Unique: Direct PDF download               │
    │   │ entry_to_meta   │    Conversion to normalized model            │
    │   └─────────────────┘                                              │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    Key Difference from OpenAlex:
    ─────────────────────────────
    - OpenAlex: Metadata only (title, abstract, citations)
    - arXiv: Full papers available (PDFs downloadable)

    This makes arXiv invaluable for building document collections
    where you need the actual paper content, not just metadata.

    Usage Examples:
    ──────────────

    # Search for papers
    async with ArxivClient() as client:
        papers = await client.search("transformer attention", max_results=10)
        for paper in papers:
            print(f"{paper.arxiv_id}: {paper.title}")

    # Download PDF
    pdf_bytes = await client.download_pdf("2301.08422")
    with open("paper.pdf", "wb") as f:
        f.write(pdf_bytes)

    Rate Limiting Warning:
    ──────────────────────
    arXiv WILL ban your IP for excessive requests.
    This client enforces 3-second delays between requests.
    Do NOT bypass rate limiting.
    """

    # =========================================================================
    # CLASS CONSTANTS
    # =========================================================================

    BASE_URL = "http://export.arxiv.org/api/query"
    # arXiv API endpoint
    # Note: Uses HTTP (not HTTPS) - this is the official endpoint
    # HTTPS redirects to HTTP anyway
    #
    # Query parameters:
    # - search_query: Search terms (see syntax below)
    # - id_list: Comma-separated arXiv IDs
    # - start: Pagination offset (0-indexed)
    # - max_results: Results per page (max ~30000)
    # - sortBy: relevance, lastUpdatedDate, submittedDate
    # - sortOrder: ascending, descending

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self):
        """
        Initialize arXiv client.

        No authentication required - arXiv API is completely open.
        Rate limiting is the only access control mechanism.

        Technical Details:
        ──────────────────
        - Timeout: 60 seconds (arXiv can be slow)
        - Rate limit: 3 seconds between requests (configurable)
        - User-Agent: Required for identification
        """
        # ─────────────────────────────────────────────────────────────────────
        # Load configuration
        # ─────────────────────────────────────────────────────────────────────
        settings = get_settings()
        self.rate_limit = settings.arxiv_rate_limit  # Default: 3.0 seconds
        # arXiv requires 3 seconds between requests
        # Violating this WILL result in IP bans

        # ─────────────────────────────────────────────────────────────────────
        # Create async HTTP client
        # ─────────────────────────────────────────────────────────────────────
        self._client = httpx.AsyncClient(
            timeout=60.0,
            # 60-second timeout (arXiv can be slow, especially for PDFs)
            # PDF downloads may take 10-30 seconds for large papers

            headers={"User-Agent": "ScientificLibraryRAG/1.0"},
            # User-Agent identifies our application
            # arXiv may block requests without User-Agent
        )

    # =========================================================================
    # RESOURCE CLEANUP
    # =========================================================================

    async def close(self) -> None:
        """
        Close HTTP client and release resources.

        Always call this when done, or use async context manager:
            async with ArxivClient() as client:
                ...
        """
        await self._client.aclose()

    # =========================================================================
    # HTTP REQUEST WITH RETRY
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        # Stop after 3 attempts total

        wait=wait_exponential(multiplier=1, min=3, max=30),
        # Exponential backoff starting from 3 seconds
        # Sequence: 3s → 6s → 12s (capped at 30s)
        #
        # Why start at 3 seconds?
        # - arXiv's rate limit is 3 seconds
        # - Starting lower could trigger rate limit on retry
    )
    async def _request(self, params: dict) -> str:
        """
        Make API request with retry logic and rate limiting.

        Args:
            params: Query parameters dict

        Returns:
            Raw XML response as string

        Raises:
            httpx.HTTPStatusError: For HTTP errors after retries

        Technical Notes:
        ────────────────
        Unlike OpenAlex (which returns JSON), arXiv returns Atom XML.
        We return the raw XML string for parsing by _parse_entry().
        """
        # ─────────────────────────────────────────────────────────────────────
        # Rate limiting - CRITICAL for arXiv
        # ─────────────────────────────────────────────────────────────────────
        await asyncio.sleep(self.rate_limit)
        # Sleep BEFORE request, not after
        # This ensures minimum 3 seconds between requests
        # NEVER remove or reduce this delay

        # ─────────────────────────────────────────────────────────────────────
        # Build URL with query parameters
        # ─────────────────────────────────────────────────────────────────────
        url = f"{self.BASE_URL}?{urlencode(params)}"
        # urlencode handles special characters in search queries
        # Example: "quantum AND computing" → "quantum%20AND%20computing"

        # ─────────────────────────────────────────────────────────────────────
        # Make request
        # ─────────────────────────────────────────────────────────────────────
        response = await self._client.get(url)
        response.raise_for_status()

        # ─────────────────────────────────────────────────────────────────────
        # Return raw XML text
        # ─────────────────────────────────────────────────────────────────────
        return response.text
        # Return text (not JSON) because arXiv returns XML

    # =========================================================================
    # XML PARSING
    # =========================================================================

    def _parse_entry(self, entry: ET.Element) -> ArxivEntry:
        """
        Parse XML entry element to ArxivEntry model.

        Args:
            entry: ElementTree Element representing one <entry>

        Returns:
            ArxivEntry Pydantic model

        XML Structure:
        ──────────────
        <entry>
          <id>http://arxiv.org/abs/2301.08422v1</id>
          <title>Paper Title</title>
          <summary>Abstract text...</summary>
          <author><name>Author Name</name></author>
          <published>2023-01-01T00:00:00Z</published>
          <updated>2023-01-02T00:00:00Z</updated>
          <arxiv:primary_category term="cs.AI"/>
          <category term="cs.AI"/>
          <arxiv:comment>10 pages, 5 figures</arxiv:comment>
          <arxiv:journal_ref>ICML 2023</arxiv:journal_ref>
          <arxiv:doi>10.1234/example</arxiv:doi>
        </entry>

        Namespace Handling:
        ───────────────────
        ElementTree requires full namespace URIs in tag names:
        - Atom elements: f"{ATOM_NS}title" → "{http://...Atom}title"
        - arXiv elements: f"{ARXIV_NS}doi" → "{http://...atom}doi"
        """
        # ─────────────────────────────────────────────────────────────────────
        # Extract arXiv ID from URL
        # ─────────────────────────────────────────────────────────────────────
        arxiv_id = entry.find(f"{ATOM_NS}id").text
        # ID comes as URL: "http://arxiv.org/abs/2301.08422v1"

        arxiv_id = arxiv_id.replace("http://arxiv.org/abs/", "")
        # Strip URL prefix to get: "2301.08422v1"

        # Remove version suffix for canonical ID
        arxiv_id_base = re.sub(r"v\d+$", "", arxiv_id)
        # Regex: v followed by digits at end of string
        # "2301.08422v1" → "2301.08422"
        # "hep-th/9901001v2" → "hep-th/9901001"

        # ─────────────────────────────────────────────────────────────────────
        # Extract and normalize title
        # ─────────────────────────────────────────────────────────────────────
        title = entry.find(f"{ATOM_NS}title").text
        title = " ".join(title.split())
        # Normalize whitespace: collapse multiple spaces/newlines into single space
        # arXiv titles often have line breaks from LaTeX source

        # ─────────────────────────────────────────────────────────────────────
        # Extract and normalize abstract (summary)
        # ─────────────────────────────────────────────────────────────────────
        summary = entry.find(f"{ATOM_NS}summary").text
        summary = " ".join(summary.split())
        # Same whitespace normalization as title

        # ─────────────────────────────────────────────────────────────────────
        # Extract authors
        # ─────────────────────────────────────────────────────────────────────
        authors = []
        for author in entry.findall(f"{ATOM_NS}author"):
            # Each author is: <author><name>Full Name</name></author>
            name = author.find(f"{ATOM_NS}name").text
            authors.append(name)
        # arXiv doesn't provide ORCIDs or affiliations in API
        # (available only on web page)

        # ─────────────────────────────────────────────────────────────────────
        # Parse dates
        # ─────────────────────────────────────────────────────────────────────
        published = entry.find(f"{ATOM_NS}published").text
        # ISO 8601 format: "2023-01-01T00:00:00Z"

        published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        # Python's fromisoformat doesn't handle "Z" suffix
        # Replace with explicit UTC offset: +00:00

        updated_elem = entry.find(f"{ATOM_NS}updated")
        updated_dt = None
        if updated_elem is not None:
            updated_dt = datetime.fromisoformat(
                updated_elem.text.replace("Z", "+00:00")
            )
        # Updated date may differ from published if paper was revised

        # ─────────────────────────────────────────────────────────────────────
        # Extract categories
        # ─────────────────────────────────────────────────────────────────────
        categories = []
        primary_category = None

        # Primary category (main classification)
        for cat in entry.findall(f"{ARXIV_NS}primary_category"):
            primary_category = cat.get("term")
            # Example: "cs.AI"

        # All categories (including cross-listings)
        for cat in entry.findall(f"{ATOM_NS}category"):
            term = cat.get("term")
            if term and term not in categories:
                categories.append(term)
        # Paper can be in multiple categories
        # Example: cs.AI, cs.LG, stat.ML

        # ─────────────────────────────────────────────────────────────────────
        # Extract optional arXiv-specific fields
        # ─────────────────────────────────────────────────────────────────────
        comment_elem = entry.find(f"{ARXIV_NS}comment")
        comment = comment_elem.text if comment_elem is not None else None
        # Comment often contains: page count, figure count, conference info
        # Example: "15 pages, 5 figures. To appear in NIPS 2023"

        journal_elem = entry.find(f"{ARXIV_NS}journal_ref")
        journal_ref = journal_elem.text if journal_elem is not None else None
        # Journal reference if paper was published
        # Example: "Nature Physics 19, 1234 (2023)"

        doi_elem = entry.find(f"{ARXIV_NS}doi")
        doi = doi_elem.text if doi_elem is not None else None
        # DOI of published version (if available)
        # arXiv papers may also have arXiv DOIs: 10.48550/arXiv.XXXX.XXXXX

        # ─────────────────────────────────────────────────────────────────────
        # Generate URLs
        # ─────────────────────────────────────────────────────────────────────
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id_base}.pdf"
        # Direct PDF link (always available)

        abs_url = f"https://arxiv.org/abs/{arxiv_id_base}"
        # Abstract page link

        # ─────────────────────────────────────────────────────────────────────
        # Build and return ArxivEntry model
        # ─────────────────────────────────────────────────────────────────────
        return ArxivEntry(
            arxiv_id=arxiv_id_base,
            title=title,
            summary=summary,
            authors=authors,
            published=published_dt,
            updated=updated_dt,
            categories=categories,
            primary_category=primary_category,
            comment=comment,
            journal_ref=journal_ref,
            doi=doi,
            pdf_url=pdf_url,
            abs_url=abs_url,
        )

    # =========================================================================
    # PUBLIC API: SEARCH
    # =========================================================================

    async def search(
        self,
        query: str,
        max_results: int = 100,
        start: int = 0,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> list[ArxivEntry]:
        """
        Search arXiv papers.

        Args:
            query: Search query (supports arXiv query syntax)
            max_results: Maximum results to return (no hard limit)
            start: Starting index for pagination (0-indexed)
            sort_by: Sort field (relevance, lastUpdatedDate, submittedDate)
            sort_order: Sort direction (ascending, descending)

        Returns:
            List of matching ArxivEntry objects

        Query Syntax:
        ─────────────
        arXiv uses a Lucene-like query syntax:

        BASIC SEARCH:
        - "quantum computing"        → Words anywhere in title/abstract
        - "quantum AND computing"    → Both words required
        - "quantum OR classical"     → Either word
        - "quantum NOT classical"    → Exclude word

        FIELD-SPECIFIC SEARCH:
        - ti:attention              → Title contains "attention"
        - au:vaswani                → Author name contains "vaswani"
        - abs:transformer           → Abstract contains "transformer"
        - cat:cs.AI                 → Category is cs.AI
        - all:neural                → All fields (default)

        COMBINING FIELDS:
        - ti:attention AND au:vaswani
        - cat:cs.AI AND ti:transformer

        WILDCARDS:
        - au:vash*                  → Author starts with "vash"
        - ti:*former                → Title ends with "former"

        Example Queries:
        ────────────────
        # All papers by Hinton on deep learning
        "au:hinton AND all:deep learning"

        # Vision transformers in cs.CV
        "cat:cs.CV AND ti:vision transformer"

        # Papers from 2023 with "GPT" in title
        "ti:GPT AND submittedDate:[2023 TO 2024]"

        Pagination:
        ───────────
        - start=0, max_results=100 → Results 0-99
        - start=100, max_results=100 → Results 100-199
        - No practical limit on max_results (but be reasonable)
        """
        # ─────────────────────────────────────────────────────────────────────
        # Build query parameters
        # ─────────────────────────────────────────────────────────────────────
        params = {
            "search_query": query,
            # Search query string with arXiv syntax

            "start": start,
            # Pagination offset (0-indexed)

            "max_results": max_results,
            # Number of results to return

            "sortBy": sort_by,
            # Sort field:
            # - relevance: Best match first
            # - lastUpdatedDate: Most recently updated first
            # - submittedDate: Most recently submitted first

            "sortOrder": sort_order,
            # ascending or descending
        }

        # ─────────────────────────────────────────────────────────────────────
        # Make request and parse XML
        # ─────────────────────────────────────────────────────────────────────
        xml_text = await self._request(params)
        root = ET.fromstring(xml_text)
        # ET.fromstring: Parse XML string into ElementTree Element

        # ─────────────────────────────────────────────────────────────────────
        # Parse each entry
        # ─────────────────────────────────────────────────────────────────────
        entries = []
        for entry in root.findall(f"{ATOM_NS}entry"):
            try:
                entries.append(self._parse_entry(entry))
            except Exception:
                continue
                # Skip malformed entries rather than failing entire search
                # Some very old arXiv entries may have unusual formatting

        return entries

    # =========================================================================
    # PUBLIC API: SEARCH BY CATEGORY
    # =========================================================================

    async def search_by_category(
        self,
        category: str,
        max_results: int = 100,
        year: Optional[int] = None,
    ) -> list[ArxivEntry]:
        """
        Search papers by arXiv category.

        Args:
            category: arXiv category code (e.g., "cs.AI", "physics.quant-ph")
            max_results: Maximum results
            year: Filter by submission year (optional)

        Returns:
            List of matching papers

        Category Examples:
        ──────────────────
        - cs.AI         Computer Science - Artificial Intelligence
        - cs.CL         Computer Science - Computation and Language
        - cs.CV         Computer Science - Computer Vision
        - cs.LG         Computer Science - Machine Learning
        - math.CO       Mathematics - Combinatorics
        - physics.quant-ph  Quantum Physics
        - stat.ML       Statistics - Machine Learning

        Year Filtering:
        ───────────────
        Uses arXiv's date range query syntax:
        submittedDate:[YYYYMMDDTTTT TO YYYYMMDDTTTT]

        Example: year=2023 → submittedDate:[202301010000 TO 202312312359]
        """
        # Build category query
        query = f"cat:{category}"

        if year:
            # arXiv uses YYYYMMDDTTTT format for date filtering
            # Add date range for entire year
            query = f"{query} AND submittedDate:[{year}01010000 TO {year}12312359]"
            # 01010000 = January 1st, 00:00
            # 12312359 = December 31st, 23:59

        return await self.search(
            query,
            max_results=max_results,
            sort_by="submittedDate",
            # Sort by submission date (newest first by default)
        )

    # =========================================================================
    # PUBLIC API: GET BY ID
    # =========================================================================

    async def get_by_id(self, arxiv_id: str) -> Optional[ArxivEntry]:
        """
        Get paper by arXiv ID.

        Args:
            arxiv_id: arXiv ID in any format:
                     - "2301.00001"
                     - "2301.00001v2"
                     - "arXiv:2301.00001"
                     - "hep-th/9901001" (old format)

        Returns:
            ArxivEntry if found, None otherwise

        ID Normalization:
        ─────────────────
        This method handles various ID formats:
        1. Strips "arXiv:" prefix if present
        2. Removes version suffix (v1, v2, etc.)
        3. Works with both old (hep-th/9901001) and new (2301.00001) formats
        """
        # ─────────────────────────────────────────────────────────────────────
        # Clean and normalize ID
        # ─────────────────────────────────────────────────────────────────────
        arxiv_id = arxiv_id.replace("arXiv:", "")
        # Remove common prefix

        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
        # Remove version suffix: "2301.00001v2" → "2301.00001"

        # ─────────────────────────────────────────────────────────────────────
        # Query by ID
        # ─────────────────────────────────────────────────────────────────────
        params = {"id_list": arxiv_id, "max_results": 1}
        # id_list: Direct ID lookup (faster than search)

        xml_text = await self._request(params)
        root = ET.fromstring(xml_text)

        entries = root.findall(f"{ATOM_NS}entry")
        if not entries:
            return None

        return self._parse_entry(entries[0])

    # =========================================================================
    # PUBLIC API: GET MULTIPLE BY IDS
    # =========================================================================

    async def get_by_ids(self, arxiv_ids: list[str]) -> list[ArxivEntry]:
        """
        Get multiple papers by arXiv IDs in single request.

        Args:
            arxiv_ids: List of arXiv IDs

        Returns:
            List of ArxivEntry objects (in same order as input)

        Efficiency Note:
        ────────────────
        This is more efficient than multiple get_by_id() calls:
        - Single HTTP request
        - Single rate limit delay
        - Batch processing

        Example:
        ────────
        ids = ["2301.00001", "2301.00002", "2301.00003"]
        papers = await client.get_by_ids(ids)
        """
        # ─────────────────────────────────────────────────────────────────────
        # Clean all IDs
        # ─────────────────────────────────────────────────────────────────────
        clean_ids = [
            re.sub(r"v\d+$", "", aid.replace("arXiv:", ""))
            for aid in arxiv_ids
        ]
        # Same normalization as get_by_id()

        # ─────────────────────────────────────────────────────────────────────
        # Query multiple IDs in single request
        # ─────────────────────────────────────────────────────────────────────
        params = {
            "id_list": ",".join(clean_ids),
            # Comma-separated list of IDs
            # Example: "2301.00001,2301.00002,2301.00003"

            "max_results": len(clean_ids),
            # Request exactly as many as we're looking for
        }

        xml_text = await self._request(params)
        root = ET.fromstring(xml_text)

        return [
            self._parse_entry(e)
            for e in root.findall(f"{ATOM_NS}entry")
        ]

    # =========================================================================
    # DATA CONVERSION: ARXIV → NORMALIZED MODEL
    # =========================================================================

    def entry_to_metadata(self, entry: ArxivEntry) -> PaperMetadata:
        """
        Convert arXiv entry to normalized PaperMetadata model.

        Args:
            entry: ArxivEntry from API

        Returns:
            PaperMetadata with source-agnostic fields

        arXiv-Specific Notes:
        ─────────────────────
        - All arXiv papers are Open Access (is_open_access=True)
        - arXiv categories stored in arxiv_categories field
        - Abstract comes from "summary" field
        - Authors are just names (no ORCIDs from API)
        - pdf_url is always available

        Comparison to OpenAlex Conversion:
        ───────────────────────────────────
        - arXiv: Simple author list (names only)
        - OpenAlex: Complex authorships (ORCIDs, institutions)

        - arXiv: Categories (cs.AI, cs.LG)
        - OpenAlex: Concepts with scores (Machine Learning: 0.95)
        """
        # ─────────────────────────────────────────────────────────────────────
        # Convert author names to Author models
        # ─────────────────────────────────────────────────────────────────────
        authors = [Author(name=name) for name in entry.authors]
        # arXiv API only provides names, not ORCIDs or affiliations
        # More detailed info available on arXiv web pages but not API

        # ─────────────────────────────────────────────────────────────────────
        # Build normalized metadata
        # ─────────────────────────────────────────────────────────────────────
        return PaperMetadata(
            arxiv_id=entry.arxiv_id,
            # arXiv ID is the primary identifier for these papers

            doi=entry.doi,
            # DOI if paper was published in journal

            title=entry.title,
            # Already normalized in _parse_entry()

            abstract=entry.summary,
            # arXiv calls it "summary" but it's the abstract

            authors=authors,
            # Simple author list

            publication_date=entry.published,
            # Datetime of first submission

            year=entry.published.year,
            # Convenience field for filtering

            journal=entry.journal_ref,
            # Journal reference if published

            arxiv_categories=entry.categories,
            # List of arXiv category codes

            is_open_access=True,
            # ALL arXiv papers are Open Access by definition

            pdf_url=entry.pdf_url,
            # Direct PDF link (always available)

            oa_url=entry.abs_url,
            # Abstract page link

            source_api="arxiv",
            # Track data source
        )

    # =========================================================================
    # PDF DOWNLOAD
    # =========================================================================

    async def download_pdf(self, arxiv_id: str) -> bytes:
        """
        Download PDF for an arXiv paper.

        Args:
            arxiv_id: arXiv ID (with or without version)

        Returns:
            PDF content as bytes

        Raises:
            httpx.HTTPStatusError: If download fails

        Usage:
        ──────
        pdf_bytes = await client.download_pdf("2301.08422")

        # Save to file
        with open("paper.pdf", "wb") as f:
            f.write(pdf_bytes)

        # Or process with PyMuPDF
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        PDF Sizes:
        ──────────
        Typical arXiv PDFs: 200KB - 5MB
        Some papers with many figures: 10-50MB
        Ensure adequate memory/storage

        Rate Limiting:
        ──────────────
        PDF downloads are subject to same rate limits as API.
        Wait 3 seconds between downloads.
        """
        # ─────────────────────────────────────────────────────────────────────
        # Normalize arXiv ID
        # ─────────────────────────────────────────────────────────────────────
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id.replace("arXiv:", ""))
        # Remove version suffix and prefix

        # ─────────────────────────────────────────────────────────────────────
        # Build PDF URL
        # ─────────────────────────────────────────────────────────────────────
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        # Standard arXiv PDF URL format

        # ─────────────────────────────────────────────────────────────────────
        # Rate limit and download
        # ─────────────────────────────────────────────────────────────────────
        await asyncio.sleep(self.rate_limit)
        # Same rate limiting as API requests

        response = await self._client.get(pdf_url)
        response.raise_for_status()

        # ─────────────────────────────────────────────────────────────────────
        # Return raw bytes
        # ─────────────────────────────────────────────────────────────────────
        return response.content
        # .content returns bytes (not text)
        # Can be written directly to file or processed in memory


# =============================================================================
#                          USAGE EXAMPLES
# =============================================================================
#
# Example 1: Search for papers on attention mechanisms
# ────────────────────────────────────────────────────
# async def search_attention_papers():
#     client = ArxivClient()
#     try:
#         papers = await client.search(
#             "ti:attention AND cat:cs.LG",
#             max_results=50,
#             sort_by="submittedDate"
#         )
#         for paper in papers:
#             print(f"{paper.arxiv_id}: {paper.title}")
#             print(f"  Categories: {', '.join(paper.categories)}")
#     finally:
#         await client.close()
#
# Example 2: Download recent ML papers
# ────────────────────────────────────
# async def download_ml_papers():
#     client = ArxivClient()
#     try:
#         papers = await client.search_by_category("cs.LG", max_results=10)
#         for paper in papers:
#             pdf = await client.download_pdf(paper.arxiv_id)
#             with open(f"{paper.arxiv_id}.pdf", "wb") as f:
#                 f.write(pdf)
#             print(f"Downloaded: {paper.arxiv_id}")
#     finally:
#         await client.close()
#
# Example 3: Get specific paper and convert to metadata
# ─────────────────────────────────────────────────────
# async def get_transformer_paper():
#     async with ArxivClient() as client:
#         paper = await client.get_by_id("1706.03762")  # Attention Is All You Need
#         if paper:
#             meta = client.entry_to_metadata(paper)
#             print(f"Title: {meta.title}")
#             print(f"Authors: {[a.name for a in meta.authors]}")
#             print(f"Year: {meta.year}")
#             print(f"PDF: {meta.pdf_url}")
# =============================================================================
