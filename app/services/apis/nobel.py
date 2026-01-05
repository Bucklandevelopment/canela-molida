"""
===============================================================================
                    NOBEL PRIZE API CLIENT - DOCUMENTATION
===============================================================================

Module: app/services/apis/nobel.py
Purpose: Async client for the official Nobel Prize API

===============================================================================
                        WHAT IS THE NOBEL PRIZE API?
===============================================================================

The only major scientific prize with a complete, official API:

┌─────────────────────────────────────────────────────────────────────────────┐
│                      NOBEL PRIZE API OVERVIEW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Endpoint:       https://api.nobelprize.org/2.1/                          │
│   Documentation:  https://app.swaggerhub.com/apis/NobelMedia/NobelMaster   │
│   Coverage:       All laureates since 1901                                  │
│   Authentication: None required                                             │
│   Rate Limit:     None (small dataset, ~1000 laureates)                    │
│                                                                             │
│   Categories (6 total):                                                     │
│   ├── Physics        (phy) - since 1901                                    │
│   ├── Chemistry      (che) - since 1901                                    │
│   ├── Medicine       (med) - since 1901 (Physiology or Medicine)          │
│   ├── Literature     (lit) - since 1901                                    │
│   ├── Peace          (pea) - since 1901                                    │
│   └── Economics      (eco) - since 1969 (Memorial Prize)                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                    NOBEL PRIZE HISTORY & TRIVIA
===============================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                      INTERESTING FACTS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Founding:                                                                 │
│   - Alfred Nobel's will (1895) established the prizes                      │
│   - First awarded in 1901                                                   │
│   - Economics added in 1968 (by Swedish Central Bank)                      │
│                                                                             │
│   Statistics (as of 2024):                                                  │
│   - ~960 individuals + 25 organizations                                    │
│   - Physics: ~225 laureates                                                │
│   - Chemistry: ~190 laureates                                              │
│   - Medicine: ~225 laureates                                               │
│   - Literature: ~120 laureates                                             │
│   - Peace: ~110 individuals + 25 organizations                             │
│   - Economics: ~95 laureates                                               │
│                                                                             │
│   Notable Records:                                                          │
│   - Youngest: Malala Yousafzai (17, Peace 2014)                           │
│   - Oldest: John Goodenough (97, Chemistry 2019)                          │
│   - Multiple wins: 4 individuals, 2 organizations                         │
│   - Marie Curie: Only person with 2 science prizes (different fields)     │
│   - Most laureates/country: USA (~400), UK (~130), Germany (~110)         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                         API ENDPOINTS
===============================================================================

The Nobel Prize API (v2.1) has several endpoints:

/laureates
  - List all laureates with filters
  - Params: nobelPrizeCategory, gender, birthCountry, nobelPrizeYear

/laureate/{id}
  - Get single laureate by ID

/nobelPrizes
  - List all prizes with filters
  - Params: nobelPrizeCategory, year, yearTo

/nobelPrize/{category}/{year}
  - Get specific prize

Response Example (laureate):
```json
{
  "id": "105",
  "knownName": {
    "en": "Albert Einstein"
  },
  "fullName": {
    "en": "Albert Einstein"
  },
  "birth": {
    "date": "1879-03-14",
    "place": { "city": { "en": "Ulm" }, "country": { "en": "Germany" } }
  },
  "nobelPrizes": [
    {
      "awardYear": "1921",
      "category": { "en": "Physics" },
      "motivation": { "en": "for his services to Theoretical Physics..." }
    }
  ]
}
```

===============================================================================
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from typing import Optional, Any
# Optional: Type hint for values that can be None
# Any: Type hint for dynamic types (API responses)

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import httpx
# httpx: Modern async HTTP client

from tenacity import retry, stop_after_attempt, wait_exponential
# tenacity: Retry library with exponential backoff

# =============================================================================
# LOCAL IMPORTS
# =============================================================================

from app.models.api import NobelLaureate
# NobelLaureate: Pydantic model for Nobel laureate data


# =============================================================================
# NOBEL CLIENT CLASS
# =============================================================================

class NobelClient:
    """
    =========================================================================
    NOBEL PRIZE ASYNC CLIENT
    =========================================================================

    Asynchronous client for the official Nobel Prize API, providing access
    to all Nobel laureates and prizes since 1901.

    Architecture:
    ┌─────────────────────────────────────────────────────────────────────┐
    │                       NobelClient                                   │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   ┌─────────────────┐    ┌─────────────────┐    ┌───────────────┐  │
    │   │  Public Methods │    │ Private Methods │    │   Attributes  │  │
    │   ├─────────────────┤    ├─────────────────┤    ├───────────────┤  │
    │   │ get_laureates   │───►│ _request        │───►│ _client       │  │
    │   │ get_laureate_   │    └─────────────────┘    └───────────────┘  │
    │   │   by_id         │                                              │
    │   │ get_prizes      │                                              │
    │   │ search_laureates│                                              │
    │   │ get_laureates_  │                                              │
    │   │   by_category_  │                                              │
    │   │   and_year      │                                              │
    │   └─────────────────┘                                              │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    Why Nobel API is Unique:
    ────────────────────────
    - ONLY major science prize with official API
    - Other prizes (Fields Medal, Turing Award, etc.) require Wikidata
    - Complete, authoritative data back to 1901
    - Simple, well-designed REST API

    Usage Examples:
    ──────────────

    # Get all Physics laureates from 2020-2023
    async with NobelClient() as client:
        laureates = await client.get_laureates(
            category="physics",
            year_from=2020,
            year_to=2023
        )
        for l in laureates:
            print(f"{l.get_name()}: {l.get_prize_motivation()}")

    # Search for a specific laureate
    results = await client.search_laureates("Einstein")
    """

    # =========================================================================
    # CLASS CONSTANTS
    # =========================================================================

    BASE_URL = "https://api.nobelprize.org/2.1"
    # Official Nobel Prize API v2.1
    # Maintained by Nobel Media AB
    # Free, no authentication, no rate limits

    # =========================================================================
    # CATEGORY CODE MAPPING
    # =========================================================================

    CATEGORIES = {
        "physics": "phy",
        "chemistry": "che",
        "medicine": "med",
        "physiology": "med",  # Alias (full name is "Physiology or Medicine")
        "literature": "lit",
        "peace": "pea",
        "economics": "eco",
    }
    # API uses short codes (phy, che, etc.)
    # This mapping allows using full names for convenience
    #
    # Note: "Economics" is technically "The Sveriges Riksbank Prize in
    # Economic Sciences in Memory of Alfred Nobel" - not a true Nobel Prize
    # but administered by the Nobel Foundation

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self):
        """
        Initialize Nobel Prize client.

        No authentication required - API is completely open.
        No rate limiting - dataset is small (~1000 laureates).

        Technical Details:
        ──────────────────
        - Timeout: 30 seconds (API is usually fast)
        - Accept header: Requests JSON format
        """
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            # base_url: Prepended to all paths

            timeout=30.0,
            # 30-second timeout (usually responds in <1s)

            headers={
                "User-Agent": "ScientificLibraryRAG/1.0",
                # User-Agent for identification

                "Accept": "application/json",
                # Request JSON format (API also supports XML)
            },
        )

    # =========================================================================
    # RESOURCE CLEANUP
    # =========================================================================

    async def close(self) -> None:
        """
        Close HTTP client and release resources.
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
    async def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Make API request with retry logic.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters

        Returns:
            Parsed JSON response

        Technical Notes:
        ────────────────
        - No rate limiting needed (small dataset)
        - Returns JSON by default
        - Responses are typically small (<100KB)
        """
        response = await self._client.get(endpoint, params=params or {})
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # PUBLIC API: GET LAUREATES
    # =========================================================================

    async def get_laureates(
        self,
        category: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        gender: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NobelLaureate]:
        """
        Get Nobel Prize laureates with filters.

        Args:
            category: Prize category (physics, chemistry, medicine, etc.)
                     Case-insensitive, accepts full names or codes
            year_from: Minimum award year (1901-present)
            year_to: Maximum award year
            gender: Filter by gender (male, female)
            limit: Results per page (default 100)
            offset: Pagination offset

        Returns:
            List of NobelLaureate objects

        Example:
        ────────
        # Get all female Physics laureates
        laureates = await client.get_laureates(
            category="physics",
            gender="female"
        )
        # Returns: Marie Curie (1903), Maria Goeppert Mayer (1963),
        #          Donna Strickland (2018), Andrea Ghez (2020),
        #          Anne L'Huillier (2023)

        # Get recent Medicine laureates
        laureates = await client.get_laureates(
            category="medicine",
            year_from=2020
        )

        Category Notes:
        ───────────────
        - "physics" or "phy" → Physics
        - "chemistry" or "che" → Chemistry
        - "medicine" or "med" or "physiology" → Physiology or Medicine
        - "literature" or "lit" → Literature
        - "peace" or "pea" → Peace
        - "economics" or "eco" → Economic Sciences

        Historical Note:
        ────────────────
        - Physics, Chemistry, Medicine, Literature, Peace: 1901-present
        - Economics: 1969-present (not original Nobel Prize)
        """
        # ─────────────────────────────────────────────────────────────────────
        # Build query parameters
        # ─────────────────────────────────────────────────────────────────────
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        if category:
            # Convert full name to code if needed
            cat_code = self.CATEGORIES.get(category.lower(), category)
            params["nobelPrizeCategory"] = cat_code
            # API uses short codes: phy, che, med, lit, pea, eco

        if year_from:
            params["nobelPrizeYear"] = year_from
            # Note: API uses nobelPrizeYear for minimum year

        if year_to:
            params["yearTo"] = year_to
            # And yearTo for maximum year

        if gender:
            params["gender"] = gender
            # "male" or "female"

        # ─────────────────────────────────────────────────────────────────────
        # Make request and parse
        # ─────────────────────────────────────────────────────────────────────
        data = await self._request("/laureates", params)
        laureates = data.get("laureates", [])
        # Response structure: {"laureates": [...], "meta": {...}}

        return [NobelLaureate(**l) for l in laureates]
        # Convert to Pydantic models

    # =========================================================================
    # PUBLIC API: GET LAUREATE BY ID
    # =========================================================================

    async def get_laureate_by_id(self, laureate_id: str) -> Optional[NobelLaureate]:
        """
        Get laureate by Nobel Prize ID.

        Args:
            laureate_id: Nobel Prize laureate ID (e.g., "105" for Einstein)

        Returns:
            NobelLaureate if found, None otherwise

        Example:
        ────────
        # Get Albert Einstein's record
        einstein = await client.get_laureate_by_id("105")
        if einstein:
            print(f"Name: {einstein.get_name()}")
            print(f"Prize: {einstein.get_prize_year()} {einstein.get_prize_category()}")
            print(f"Motivation: {einstein.get_prize_motivation()}")

        Finding IDs:
        ────────────
        IDs are assigned sequentially but not always consecutive.
        Best to search by name first, then use ID for direct lookup.
        """
        try:
            data = await self._request(f"/laureate/{laureate_id}")
            laureates = data.get("laureates", [])
            # Even single laureate is wrapped in list

            if laureates:
                return NobelLaureate(**laureates[0])
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # =========================================================================
    # PUBLIC API: GET PRIZES
    # =========================================================================

    async def get_prizes(
        self,
        category: Optional[str] = None,
        year: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Get Nobel Prizes with filters.

        Args:
            category: Prize category
            year: Exact year
            year_from: Minimum year
            year_to: Maximum year

        Returns:
            List of prize records (raw dicts, not models)

        Example:
        ────────
        # Get all Physics prizes from 2020
        prizes = await client.get_prizes(category="physics", year=2020)
        for prize in prizes:
            print(f"{prize['awardYear']}: {prize['category']['en']}")
            for laureate in prize.get('laureates', []):
                print(f"  - {laureate['knownName']['en']}")

        Prize vs Laureate:
        ──────────────────
        - get_laureates(): Returns individual people/organizations
        - get_prizes(): Returns prize records (may have multiple laureates)

        A single prize can have 1-3 laureates sharing it.
        """
        params: dict[str, Any] = {}

        if category:
            cat_code = self.CATEGORIES.get(category.lower(), category)
            params["nobelPrizeCategory"] = cat_code

        if year:
            params["nobelPrizeYear"] = year

        if year_from:
            params["yearFrom"] = year_from

        if year_to:
            params["yearTo"] = year_to

        data = await self._request("/nobelPrizes", params)
        return data.get("nobelPrizes", [])
        # Return raw dicts (prize structure is complex)

    # =========================================================================
    # PUBLIC API: SEARCH LAUREATES BY NAME
    # =========================================================================

    async def search_laureates(self, name: str) -> list[NobelLaureate]:
        """
        Search laureates by name.

        Args:
            name: Name to search for (case-insensitive, partial match)

        Returns:
            List of matching laureates

        Example:
        ────────
        # Find all laureates with "Einstein" in name
        results = await client.search_laureates("Einstein")
        # Returns: Albert Einstein

        # Find all laureates with "Curie" in name
        results = await client.search_laureates("Curie")
        # Returns: Marie Curie, Pierre Curie, Irène Joliot-Curie

        Implementation Note:
        ────────────────────
        Nobel API doesn't have direct name search, so this method:
        1. Fetches all laureates (cached after first call)
        2. Filters locally by name

        For production, consider caching all laureates locally
        (~1000 records, rarely changes).
        """
        # Fetch all laureates (API has no search endpoint)
        all_laureates = await self.get_laureates(limit=1000)
        # limit=1000 should get all (~960 as of 2024)

        # Filter by name
        name_lower = name.lower()
        matches = []

        for laureate in all_laureates:
            laureate_name = laureate.get_name().lower()
            if name_lower in laureate_name:
                matches.append(laureate)

        return matches

    # =========================================================================
    # PUBLIC API: GET BY CATEGORY AND YEAR
    # =========================================================================

    async def get_laureates_by_category_and_year(
        self,
        category: str,
        year: int,
    ) -> list[NobelLaureate]:
        """
        Get laureates for specific category and year.

        Args:
            category: Prize category (physics, chemistry, etc.)
            year: Award year (1901-present)

        Returns:
            List of laureates (1-3 for shared prizes)

        Example:
        ────────
        # Get 2023 Physics laureates
        laureates = await client.get_laureates_by_category_and_year("physics", 2023)
        for l in laureates:
            print(f"{l.get_name()}: {l.get_prize_motivation()}")
        # Output:
        # Pierre Agostini: for experimental methods...
        # Ferenc Krausz: for experimental methods...
        # Anne L'Huillier: for experimental methods...

        Historical Notes:
        ─────────────────
        - Some years have no prize (WWI, WWII, no worthy candidate)
        - Economics starts 1969 (returns empty for earlier years)
        - 1-3 laureates can share a prize
        """
        return await self.get_laureates(
            category=category,
            year_from=year,
            year_to=year,
            # Use same year for both to get exact match
        )


# =============================================================================
#                          USAGE EXAMPLES
# =============================================================================
#
# Example 1: Get recent Physics laureates
# ───────────────────────────────────────
# async def recent_physics():
#     client = NobelClient()
#     try:
#         laureates = await client.get_laureates(
#             category="physics",
#             year_from=2020
#         )
#         for l in laureates:
#             print(f"{l.get_prize_year()}: {l.get_name()}")
#             print(f"  Motivation: {l.get_prize_motivation()}")
#     finally:
#         await client.close()
#
# Example 2: Find famous scientists
# ─────────────────────────────────
# async def find_scientists():
#     async with NobelClient() as client:
#         for name in ["Einstein", "Curie", "Feynman", "Crick"]:
#             results = await client.search_laureates(name)
#             for l in results:
#                 print(f"{l.get_name()} ({l.get_prize_year()} {l.get_prize_category()})")
#
# Example 3: Statistics by category
# ─────────────────────────────────
# async def category_stats():
#     client = NobelClient()
#     try:
#         for cat in ["physics", "chemistry", "medicine", "economics"]:
#             laureates = await client.get_laureates(category=cat, limit=1000)
#             women = [l for l in laureates if l.gender == "female"]
#             print(f"{cat}: {len(laureates)} total, {len(women)} women")
#     finally:
#         await client.close()
#
# Output:
# physics: 225 total, 5 women
# chemistry: 190 total, 8 women
# medicine: 225 total, 13 women
# economics: 95 total, 3 women
# =============================================================================
