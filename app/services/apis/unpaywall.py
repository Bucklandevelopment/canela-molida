"""
===============================================================================
                    UNPAYWALL API CLIENT - DOCUMENTATION
===============================================================================

Module: app/services/apis/unpaywall.py
Purpose: Async client for Unpaywall, finding Open Access versions of papers

===============================================================================
                         WHAT IS UNPAYWALL?
===============================================================================

Unpaywall is a service that finds legal Open Access versions of papers:

┌─────────────────────────────────────────────────────────────────────────────┐
│                        UNPAYWALL OVERVIEW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Purpose:       Find free legal versions of academic papers                │
│   Coverage:      47M+ free articles (growing daily)                         │
│   Input:         DOI (Digital Object Identifier)                           │
│   Output:        URLs to OA versions (PDF, HTML, repository)               │
│                                                                             │
│   Operated by:   OurResearch (same non-profit as OpenAlex)                 │
│   License:       Data is CC0 (completely free)                             │
│   Used by:       Browser extensions, library systems, APIs                 │
│                                                                             │
│   Rate Limit:    100,000 requests/day with email                           │
│                  (~1.15 requests/second sustained)                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                     OPEN ACCESS TYPES EXPLAINED
===============================================================================

Unpaywall classifies OA into several categories:

┌─────────────────────────────────────────────────────────────────────────────┐
│                     OPEN ACCESS TAXONOMY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   GOLD OA                                                                   │
│   ───────                                                                   │
│   Published in fully OA journal (e.g., PLOS, BMC, eLife)                   │
│   Article is free on publisher site                                         │
│   Usually CC-BY license                                                     │
│   Author often pays APC (Article Processing Charge)                         │
│                                                                             │
│   GREEN OA                                                                  │
│   ────────                                                                  │
│   Deposited in repository (institutional, subject-based)                   │
│   May be preprint, postprint, or published version                         │
│   Examples: PubMed Central, arXiv, university repositories                 │
│   Free for authors                                                          │
│                                                                             │
│   BRONZE OA                                                                 │
│   ─────────                                                                 │
│   Free to read on publisher site, but no clear OA license                  │
│   May become paywalled later (not permanently open)                        │
│   Common for older articles or special promotions                          │
│                                                                             │
│   HYBRID OA                                                                 │
│   ─────────                                                                 │
│   OA article in otherwise subscription journal                             │
│   Author paid APC for open access                                           │
│   Journal charges both subscriptions and APCs ("double dipping")           │
│                                                                             │
│   CLOSED                                                                    │
│   ──────                                                                    │
│   No free legal version found                                               │
│   May still exist (Unpaywall doesn't find everything)                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                    UNPAYWALL RESPONSE STRUCTURE
===============================================================================

When you query Unpaywall with a DOI, you get:

```json
{
  "doi": "10.1038/nature12373",
  "is_oa": true,
  "oa_status": "green",                    // gold, green, bronze, hybrid, closed
  "best_oa_location": {                    // Best available version
    "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567",
    "url_for_pdf": "https://...pdf",       // Direct PDF if available
    "version": "publishedVersion",         // acceptedVersion, submittedVersion
    "license": "cc-by",                    // License if known
    "host_type": "repository"              // publisher, repository
  },
  "oa_locations": [                        // All available versions
    { ... },
    { ... }
  ],
  "title": "Paper Title",
  "year": 2023,
  "journal_name": "Nature"
}
```

Version Types:
──────────────
- submittedVersion: Preprint (before peer review)
- acceptedVersion: Postprint (after peer review, before publisher formatting)
- publishedVersion: Final publisher version (Version of Record)

===============================================================================
                         WHY USE UNPAYWALL?
===============================================================================

Workflow for PDF Retrieval:
─────────────────────────

1. You have a DOI from OpenAlex/Crossref/etc.
2. You want the PDF for full-text analysis
3. Publisher site requires subscription
4. Use Unpaywall to find legal free version

                    ┌─────────────┐
                    │    DOI      │
                    │ 10.1038/... │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Unpaywall  │
                    │   Query     │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌───────────┐    ┌───────────┐    ┌───────────┐
   │ PubMed    │    │ Publisher │    │ Instit.   │
   │ Central   │    │ OA        │    │ Repo      │
   └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
                          ▼
                    ┌───────────┐
                    │    PDF    │
                    │ Download  │
                    └───────────┘

===============================================================================
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import asyncio
# asyncio: Python's async I/O framework
# Used for: Rate limiting delays in batch operations

from typing import Optional
# Optional: Type hint for values that can be None

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import httpx
# httpx: Modern async HTTP client
# See openalex.py for detailed comparison

from tenacity import retry, stop_after_attempt, wait_exponential
# tenacity: Retry library with exponential backoff
# See openalex.py for detailed explanation

# =============================================================================
# LOCAL IMPORTS
# =============================================================================

from app.core.config import get_settings
# get_settings(): Singleton configuration loader
# Provides: unpaywall_email (required for API access)

from app.models.api import UnpaywallResponse
# UnpaywallResponse: Pydantic model for Unpaywall API responses
# Key fields: doi, is_oa, oa_status, best_oa_location, oa_locations


# =============================================================================
# UNPAYWALL CLIENT CLASS
# =============================================================================

class UnpaywallClient:
    """
    =========================================================================
    UNPAYWALL ASYNC CLIENT
    =========================================================================

    Asynchronous client for the Unpaywall API, finding Open Access versions
    of papers by their DOI.

    Architecture:
    ┌─────────────────────────────────────────────────────────────────────┐
    │                     UnpaywallClient                                 │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   ┌─────────────────┐    ┌─────────────────┐    ┌───────────────┐  │
    │   │  Public Methods │    │ Private Methods │    │   Attributes  │  │
    │   ├─────────────────┤    ├─────────────────┤    ├───────────────┤  │
    │   │ get_oa_location │───►│ _request        │───►│ _client       │  │
    │   │ batch_get_oa_   │    └─────────────────┘    │ email         │  │
    │   │   locations     │                           └───────────────┘  │
    │   │ get_pdf_url     │    Convenience method                        │
    │   └─────────────────┘                                              │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    Why Unpaywall is Essential:
    ───────────────────────────
    - OpenAlex: Has pdf_url field, but often empty
    - arXiv: Only covers preprints in specific fields
    - Publisher sites: Require subscriptions

    Unpaywall aggregates OA versions from:
    - PubMed Central (~8M articles)
    - arXiv, bioRxiv, medRxiv
    - Institutional repositories (1000s)
    - Publisher OA (gold, hybrid, bronze)
    - Author personal pages

    Usage Examples:
    ──────────────

    # Check if paper is OA and get PDF URL
    async with UnpaywallClient() as client:
        result = await client.get_oa_location("10.1038/nature12373")
        if result and result.is_oa:
            print(f"PDF available at: {result.get_pdf_url()}")

    # Quick PDF URL lookup
    pdf_url = await client.get_pdf_url("10.1038/nature12373")

    Limitations:
    ────────────
    - Only works with DOIs (not arXiv IDs, PMIDs, etc.)
    - Some green OA versions are embargoed
    - PDF URLs may expire or change
    - Coverage is good (~50% of papers have OA) but not complete
    """

    # =========================================================================
    # CLASS CONSTANTS
    # =========================================================================

    BASE_URL = "https://api.unpaywall.org/v2"
    # Unpaywall API v2 endpoint
    #
    # Endpoint format: /{doi}?email=your@email.com
    # Example: /10.1038/nature12373?email=user@example.com
    #
    # Returns JSON with OA information

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self, email: Optional[str] = None):
        """
        Initialize Unpaywall client.

        Args:
            email: Required email for API access
                   Used for rate limiting and abuse prevention
                   Falls back to settings.unpaywall_email

        Raises:
            ValueError: If no email provided and none in settings

        Email Requirement:
        ──────────────────
        Unpaywall requires an email for all API requests.
        This is used to:
        - Track usage (100K/day limit)
        - Contact users about abuse
        - Identify legitimate vs. scraping requests

        No authentication/API key required - just email.
        """
        # ─────────────────────────────────────────────────────────────────────
        # Load configuration and validate email
        # ─────────────────────────────────────────────────────────────────────
        settings = get_settings()
        self.email = email or settings.unpaywall_email

        if not self.email:
            raise ValueError("Email required for Unpaywall API")
            # Unlike OpenAlex where email is optional (just slower),
            # Unpaywall REQUIRES an email - requests fail without it

        # ─────────────────────────────────────────────────────────────────────
        # Create async HTTP client
        # ─────────────────────────────────────────────────────────────────────
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            # base_url: Prepended to all paths

            timeout=30.0,
            # 30-second timeout
            # Unpaywall is usually fast (<1s) but can be slow during peak

            headers={"User-Agent": "ScientificLibraryRAG/1.0"},
            # User-Agent for identification
        )

    # =========================================================================
    # RESOURCE CLEANUP
    # =========================================================================

    async def close(self) -> None:
        """
        Close HTTP client and release resources.

        Always call when done, or use async context manager:
            async with UnpaywallClient() as client:
                ...
        """
        await self._client.aclose()

    # =========================================================================
    # HTTP REQUEST WITH RETRY
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        # Stop after 3 attempts

        wait=wait_exponential(multiplier=1, min=1, max=10),
        # Exponential backoff: 1s → 2s → 4s (max 10s)
    )
    async def _request(self, endpoint: str) -> dict:
        """
        Make API request with retry logic.

        Args:
            endpoint: API endpoint (DOI path)

        Returns:
            Parsed JSON response

        Technical Notes:
        ────────────────
        - Email is passed as query parameter (required)
        - No rate limiting delay (100K/day is generous)
        - Returns JSON (not XML like arXiv)
        """
        response = await self._client.get(
            endpoint,
            params={"email": self.email},
            # Email is required in every request
            # Unpaywall uses this for rate limiting
        )
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # PUBLIC API: GET OA LOCATION
    # =========================================================================

    async def get_oa_location(self, doi: str) -> Optional[UnpaywallResponse]:
        """
        Get Open Access location for a DOI.

        Args:
            doi: Digital Object Identifier (with or without URL prefix)
                 Examples: "10.1038/nature12373"
                          "https://doi.org/10.1038/nature12373"

        Returns:
            UnpaywallResponse with OA information, or None if DOI not found

        Response Fields:
        ────────────────
        - is_oa: Boolean - is any OA version available?
        - oa_status: String - gold, green, bronze, hybrid, closed
        - best_oa_location: Dict - best available version
          - url: Landing page URL
          - url_for_pdf: Direct PDF URL (if available)
          - version: submittedVersion, acceptedVersion, publishedVersion
          - license: cc-by, cc0, etc. (if known)
          - host_type: publisher, repository

        - oa_locations: List - all available versions (may be multiple)

        Example:
        ────────
        result = await client.get_oa_location("10.1038/nature12373")
        if result and result.is_oa:
            pdf_url = result.best_oa_location.get("url_for_pdf")
            if pdf_url:
                print(f"PDF available at: {pdf_url}")
            else:
                print(f"HTML version at: {result.best_oa_location.get('url')}")
        else:
            print("No OA version found")

        Coverage Notes:
        ───────────────
        - ~50% of DOIs have some OA version
        - Recent papers more likely to have OA (policies improving)
        - Some disciplines (biology, medicine) have higher OA rates
        - Not finding OA doesn't mean it doesn't exist (database lag)
        """
        # ─────────────────────────────────────────────────────────────────────
        # Clean DOI (remove URL prefix if present)
        # ─────────────────────────────────────────────────────────────────────
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        # Common mistake: passing full DOI URL
        # "https://doi.org/10.1038/..." → "10.1038/..."

        try:
            # ─────────────────────────────────────────────────────────────────
            # Query Unpaywall
            # ─────────────────────────────────────────────────────────────────
            data = await self._request(f"/{doi}")
            # Endpoint is simply /{doi}
            # Example: /10.1038/nature12373

            return UnpaywallResponse(**data)
            # Parse into Pydantic model for validation and type hints

        except httpx.HTTPStatusError as e:
            # ─────────────────────────────────────────────────────────────────
            # Handle 404: DOI not found
            # ─────────────────────────────────────────────────────────────────
            if e.response.status_code == 404:
                return None
                # 404 means DOI not in Unpaywall database
                # This happens for:
                # - Invalid DOIs
                # - Very new papers (not yet indexed)
                # - Some publishers that don't share metadata
            raise
            # Re-raise other errors for retry

    # =========================================================================
    # PUBLIC API: BATCH GET OA LOCATIONS
    # =========================================================================

    async def batch_get_oa_locations(
        self,
        dois: list[str],
        delay: float = 0.1,
    ) -> dict[str, Optional[UnpaywallResponse]]:
        """
        Get OA locations for multiple DOIs.

        Args:
            dois: List of DOIs to look up
            delay: Delay between requests (seconds)
                   Default 0.1s = 10 req/s (well under 100K/day limit)

        Returns:
            Dict mapping DOI to UnpaywallResponse (or None if not found)

        Example:
        ────────
        dois = ["10.1038/nature12373", "10.1126/science.1234567"]
        results = await client.batch_get_oa_locations(dois)

        for doi, result in results.items():
            if result and result.is_oa:
                print(f"{doi}: OA available")
            else:
                print(f"{doi}: No OA found")

        Performance Notes:
        ──────────────────
        - Sequential requests (Unpaywall has no batch endpoint)
        - At 10 req/s, 1000 DOIs takes ~100 seconds
        - Consider caching results for repeated lookups
        - For large-scale needs, use Unpaywall data dump

        Rate Limit Math:
        ────────────────
        100,000 requests/day ÷ 86,400 seconds = 1.15 req/s sustained
        But bursting at 10 req/s is fine for short periods
        """
        results = {}

        for doi in dois:
            try:
                results[doi] = await self.get_oa_location(doi)
            except Exception:
                results[doi] = None
                # Continue on errors (don't fail entire batch)

            await asyncio.sleep(delay)
            # Small delay between requests to be polite
            # Not strictly required, but good practice

        return results

    # =========================================================================
    # PUBLIC API: GET PDF URL (CONVENIENCE METHOD)
    # =========================================================================

    async def get_pdf_url(self, doi: str) -> Optional[str]:
        """
        Get direct PDF URL for a DOI if available.

        Args:
            doi: Digital Object Identifier

        Returns:
            PDF URL if available, None otherwise

        This is a convenience method that:
        1. Calls get_oa_location()
        2. Checks if paper is OA
        3. Extracts PDF URL from best_oa_location

        Example:
        ────────
        pdf_url = await client.get_pdf_url("10.1038/nature12373")
        if pdf_url:
            # Download PDF
            async with httpx.AsyncClient() as http:
                response = await http.get(pdf_url)
                with open("paper.pdf", "wb") as f:
                    f.write(response.content)

        Important Notes:
        ────────────────
        - Returns None if:
          - DOI not found in Unpaywall
          - Paper is not OA (is_oa=False)
          - No PDF URL in best_oa_location (HTML-only version)

        - PDF URLs can be:
          - Direct links (publisher or repository)
          - May require following redirects
          - May have usage restrictions despite being "free"
        """
        result = await self.get_oa_location(doi)

        if result and result.is_oa:
            return result.get_pdf_url()
            # get_pdf_url() is a helper method on UnpaywallResponse
            # that extracts url_for_pdf from best_oa_location

        return None


# =============================================================================
#                          USAGE EXAMPLES
# =============================================================================
#
# Example 1: Check OA status of a paper
# ─────────────────────────────────────
# async def check_oa():
#     client = UnpaywallClient(email="your@email.com")
#     try:
#         result = await client.get_oa_location("10.1038/nature12373")
#         if result:
#             print(f"Is OA: {result.is_oa}")
#             print(f"OA Status: {result.oa_status}")
#             if result.is_oa:
#                 loc = result.best_oa_location
#                 print(f"Version: {loc.get('version')}")
#                 print(f"Host: {loc.get('host_type')}")
#                 print(f"PDF: {loc.get('url_for_pdf')}")
#     finally:
#         await client.close()
#
# Example 2: Batch lookup for paper collection
# ────────────────────────────────────────────
# async def find_oa_versions(dois: list[str]):
#     async with UnpaywallClient() as client:
#         results = await client.batch_get_oa_locations(dois)
#
#         oa_papers = []
#         for doi, result in results.items():
#             if result and result.is_oa:
#                 pdf_url = result.get_pdf_url()
#                 if pdf_url:
#                     oa_papers.append({
#                         "doi": doi,
#                         "pdf_url": pdf_url,
#                         "version": result.best_oa_location.get("version")
#                     })
#
#         return oa_papers
#
# Example 3: Integration with OpenAlex
# ────────────────────────────────────
# async def get_paper_with_pdf(doi: str):
#     """Get paper metadata from OpenAlex and PDF from Unpaywall."""
#     from app.services.apis import OpenAlexClient, UnpaywallClient
#
#     openalex = OpenAlexClient()
#     unpaywall = UnpaywallClient()
#
#     try:
#         # Get metadata
#         work = await openalex.get_work_by_doi(doi)
#         metadata = openalex.work_to_metadata(work)
#
#         # Get PDF URL
#         pdf_url = await unpaywall.get_pdf_url(doi)
#         if pdf_url:
#             metadata.pdf_url = pdf_url
#
#         return metadata
#     finally:
#         await openalex.close()
#         await unpaywall.close()
# =============================================================================
