"""
===============================================================================
                    WIKIDATA SPARQL CLIENT - DOCUMENTATION
===============================================================================

Module: app/services/apis/wikidata.py
Purpose: Async client for Wikidata SPARQL, querying scientific prizes

===============================================================================
                         WHAT IS WIKIDATA?
===============================================================================

Wikidata is a free, collaborative knowledge base:

┌─────────────────────────────────────────────────────────────────────────────┐
│                        WIKIDATA OVERVIEW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   What:         Structured data behind Wikipedia                           │
│   Size:         100M+ items (entities)                                     │
│   License:      CC0 (Public Domain)                                        │
│   Query:        SPARQL endpoint                                            │
│   Endpoint:     https://query.wikidata.org/sparql                          │
│                                                                             │
│   Key Features:                                                             │
│   - Every entity has a unique Q-ID (Q42 = Douglas Adams)                   │
│   - Properties have P-IDs (P166 = award received)                          │
│   - Multilingual (labels in 300+ languages)                                │
│   - Linked to Wikipedia, scholarly databases, and more                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                    WHY WIKIDATA FOR SCIENTIFIC PRIZES?
===============================================================================

Most scientific prizes lack official APIs. Wikidata fills this gap:

┌─────────────────────────────────────────────────────────────────────────────┐
│                 SCIENTIFIC PRIZES IN WIKIDATA                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   MATHEMATICS                                                               │
│   ├── Fields Medal (Q28835) - "Nobel of Mathematics"                       │
│   │   Since 1936, awarded every 4 years, age limit 40                      │
│   ├── Abel Prize (Q160042) - Since 2003, no age limit                      │
│   ├── Wolf Prize in Mathematics (Q194351) - Since 1978                     │
│   └── Breakthrough Prize in Mathematics (Q15046788) - Since 2013           │
│                                                                             │
│   COMPUTER SCIENCE                                                          │
│   ├── Turing Award (Q185667) - "Nobel of Computing"                        │
│   │   Since 1966, awarded by ACM                                           │
│   └── Breakthrough Prize in Fundamental Physics (Q16988195)                │
│                                                                             │
│   PHYSICS                                                                   │
│   ├── Wolf Prize in Physics (Q694251)                                      │
│   ├── Kavli Prize in Astrophysics (Q1164862)                               │
│   ├── Kavli Prize in Nanoscience (Q1164863)                                │
│   └── Shaw Prize in Astronomy (Q1364556)                                   │
│                                                                             │
│   LIFE SCIENCES                                                             │
│   ├── Lasker Award (Basic Medical Research) (Q645891)                      │
│   ├── Lasker Award (Clinical Research) (Q645892)                           │
│   ├── Kavli Prize in Neuroscience (Q1164864)                               │
│   └── Breakthrough Prize in Life Sciences (Q16988211)                      │
│                                                                             │
│   CHEMISTRY                                                                 │
│   └── Wolf Prize in Chemistry (Q852298)                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                           SPARQL BASICS
===============================================================================

SPARQL (SPARQL Protocol and RDF Query Language) queries Wikidata:

Basic Structure:
────────────────

```sparql
SELECT ?person ?personLabel ?year
WHERE {
  ?person p:P166 ?awardStatement .           # P166 = award received
  ?awardStatement ps:P166 wd:Q28835 .        # Q28835 = Fields Medal
  OPTIONAL { ?awardStatement pq:P585 ?date } # P585 = point in time

  SERVICE wikibase:label {                   # Get human-readable labels
    bd:serviceParam wikibase:language "en".
  }
}
ORDER BY DESC(?year)
LIMIT 100
```

Key Prefixes:
─────────────
- wd:    Wikidata entity (wd:Q28835 = Fields Medal)
- wdt:   Direct property (wdt:P166 = award received, simple)
- p:     Property statement (p:P166 = award statement)
- ps:    Property statement value
- pq:    Property qualifier (e.g., date of award)

Property Structure:
───────────────────

Wikidata uses "statements" with qualifiers:

    Person ─── p:P166 ───► Statement
                               │
                               ├── ps:P166 ───► Fields Medal (Q28835)
                               ├── pq:P585 ───► 2022-07-05 (date)
                               └── pq:P108 ───► MIT (affiliation)

This allows attaching metadata (date, location, etc.) to each fact.

===============================================================================
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from datetime import datetime
# datetime: Date/time handling
# Used for: Parsing award dates from SPARQL results

from typing import Optional, Any
# Optional: Type hint for values that can be None
# Any: Type hint for dynamic types

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

from app.models.api import WikidataEntity
# WikidataEntity: Pydantic model for Wikidata entity data


# =============================================================================
# WIKIDATA CLIENT CLASS
# =============================================================================

class WikidataClient:
    """
    =========================================================================
    WIKIDATA SPARQL ASYNC CLIENT
    =========================================================================

    Asynchronous client for Wikidata SPARQL endpoint, specialized for
    querying scientific prize winners.

    Architecture:
    ┌─────────────────────────────────────────────────────────────────────┐
    │                     WikidataClient                                  │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │   ┌─────────────────────────┐   ┌─────────────────┐                │
    │   │    Generic Methods      │   │  Prize-Specific │                │
    │   ├─────────────────────────┤   ├─────────────────┤                │
    │   │ get_prize_winners       │   │ get_fields_     │                │
    │   │ search_scientist        │   │   medal_winners │                │
    │   │ get_scientist_prizes    │   │ get_turing_     │                │
    │   └───────────┬─────────────┘   │   award_winners │                │
    │               │                 │ get_abel_prize_ │                │
    │               ▼                 │   winners       │                │
    │       ┌───────────────┐         │ get_breakthrough│                │
    │       │   _query      │         │ get_wolf_prize  │                │
    │       │  (SPARQL)     │         └─────────────────┘                │
    │       └───────────────┘                                            │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    Why Wikidata for Prizes:
    ────────────────────────
    - Nobel: Has official API (use NobelClient instead)
    - Fields Medal: No API, use Wikidata
    - Turing Award: ACM has no public API, use Wikidata
    - Abel Prize: No API, use Wikidata
    - Wolf Prize: No API, use Wikidata
    - Breakthrough Prize: No API, use Wikidata

    Usage Examples:
    ──────────────

    # Get Fields Medal winners from 2022
    async with WikidataClient() as client:
        winners = await client.get_fields_medal_winners(year=2022)
        for w in winners:
            print(f"{w.label}: {w.description}")

    # Get all prizes won by a scientist
    prizes = await client.get_scientist_prizes("Q937")  # Albert Einstein

    Limitations:
    ────────────
    - SPARQL queries can be slow (1-10 seconds)
    - Data quality varies (community-edited)
    - Rate limits exist (~5 req/s sustained)
    - Complex queries may timeout
    """

    # =========================================================================
    # CLASS CONSTANTS
    # =========================================================================

    SPARQL_URL = "https://query.wikidata.org/sparql"
    # Wikidata Query Service endpoint
    # Runs Blazegraph SPARQL engine
    # Free, no authentication required

    # =========================================================================
    # PRIZE Q-IDs MAPPING
    # =========================================================================

    PRIZE_IDS = {
        # Mathematics
        "fields_medal": "Q28835",
        # Fields Medal - Highest honor in mathematics
        # Awarded every 4 years at International Congress of Mathematicians
        # Recipients must be under 40 years old

        "turing_award": "Q185667",
        # ACM A.M. Turing Award - "Nobel of Computing"
        # Named after Alan Turing
        # Awarded annually since 1966

        "abel_prize": "Q160042",
        # Abel Prize - Mathematics lifetime achievement
        # Awarded by Norwegian Academy since 2003
        # No age restriction (unlike Fields Medal)

        # Breakthrough Prizes (Silicon Valley philanthropists)
        "breakthrough_math": "Q15046788",
        "breakthrough_physics": "Q16988195",
        "breakthrough_life": "Q16988211",

        # Wolf Prizes (Wolf Foundation, Israel)
        "wolf_prize_math": "Q194351",
        "wolf_prize_physics": "Q694251",
        "wolf_prize_chemistry": "Q852298",

        # Kavli Prizes (Kavli Foundation, Norway)
        "kavli_astrophysics": "Q1164862",
        "kavli_nanoscience": "Q1164863",
        "kavli_neuroscience": "Q1164864",

        # Lasker Awards (often precedes Nobel in Medicine)
        "lasker_basic": "Q645891",
        "lasker_clinical": "Q645892",

        # Shaw Prizes ("Nobel of the East", Hong Kong)
        "shaw_astronomy": "Q1364556",
        "shaw_life_science": "Q1364557",
        "shaw_math": "Q1364558",
    }
    # These Q-IDs are stable identifiers in Wikidata
    # Use PRIZE_IDS["fields_medal"] to get "Q28835"

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self):
        """
        Initialize Wikidata SPARQL client.

        No authentication required.
        Rate limit: ~5 requests/second sustained (be polite).

        Technical Details:
        ──────────────────
        - Timeout: 60 seconds (SPARQL can be slow)
        - Accept header: Requests JSON results
        """
        self._client = httpx.AsyncClient(
            timeout=60.0,
            # 60-second timeout
            # Complex SPARQL queries can take 5-30 seconds
            # Timeout prevents hanging on pathological queries

            headers={
                "User-Agent": "ScientificLibraryRAG/1.0",
                # User-Agent: Required by Wikidata
                # Requests without User-Agent may be blocked

                "Accept": "application/sparql-results+json",
                # Request JSON format for results
                # Alternative: XML, CSV, TSV
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
    # SPARQL QUERY EXECUTION
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        # Stop after 3 attempts

        wait=wait_exponential(multiplier=1, min=2, max=30),
        # Exponential backoff: 2s → 4s → 8s (max 30s)
        # Longer waits because SPARQL server may be under load
    )
    async def _query(self, sparql: str) -> list[dict[str, Any]]:
        """
        Execute SPARQL query and return results.

        Args:
            sparql: SPARQL query string

        Returns:
            List of result bindings (each result is a dict)

        SPARQL Response Format:
        ───────────────────────

        {
          "results": {
            "bindings": [
              {
                "person": {"type": "uri", "value": "http://...Q937"},
                "personLabel": {"type": "literal", "value": "Albert Einstein"},
                "year": {"type": "literal", "value": "1921"}
              },
              ...
            ]
          }
        }

        We extract the "bindings" list and return it.
        """
        response = await self._client.get(
            self.SPARQL_URL,
            params={
                "query": sparql,
                # The SPARQL query text

                "format": "json",
                # Request JSON format
                # (redundant with Accept header, but some clients need both)
            },
        )
        response.raise_for_status()

        data = response.json()
        return data.get("results", {}).get("bindings", [])
        # Extract bindings from nested response structure

    # =========================================================================
    # PUBLIC API: GET PRIZE WINNERS
    # =========================================================================

    async def get_prize_winners(
        self,
        prize_qid: str,
        year: Optional[int] = None,
        limit: int = 100,
    ) -> list[WikidataEntity]:
        """
        Get winners of a specific prize.

        Args:
            prize_qid: Wikidata Q-ID of the prize (e.g., "Q28835" for Fields Medal)
            year: Filter by award year (optional)
            limit: Maximum results

        Returns:
            List of prize winners as WikidataEntity objects

        SPARQL Query Explanation:
        ─────────────────────────

        ```sparql
        SELECT ?person ?personLabel ?personDescription
               (YEAR(?date) as ?year) ?affiliationLabel
        WHERE {
          ?person p:P166 ?awardStatement .        # Has award statement
          ?awardStatement ps:P166 wd:Q28835 .     # Award is Fields Medal
          OPTIONAL { ?awardStatement pq:P585 ?date }  # Award date
          OPTIONAL { ?awardStatement pq:P108 ?affiliation }  # Affiliation

          SERVICE wikibase:label {                # Get labels
            bd:serviceParam wikibase:language "en,es".
          }
        }
        ORDER BY DESC(?year)
        LIMIT 100
        ```

        Key Properties:
        ───────────────
        - P166: award received
        - P585: point in time (date qualifier)
        - P108: employer/affiliation

        Example:
        ────────
        # Get all Fields Medal winners
        winners = await client.get_prize_winners("Q28835")

        # Get 2022 Fields Medal winners
        winners = await client.get_prize_winners("Q28835", year=2022)
        # Returns: Hugo Duminil-Copin, June Huh, James Maynard, Maryna Viazovska
        """
        # ─────────────────────────────────────────────────────────────────────
        # Build year filter if specified
        # ─────────────────────────────────────────────────────────────────────
        year_filter = ""
        if year:
            year_filter = f'FILTER(YEAR(?date) = {year})'
            # SPARQL FILTER restricts results
            # YEAR() extracts year from datetime

        # ─────────────────────────────────────────────────────────────────────
        # Construct SPARQL query
        # ─────────────────────────────────────────────────────────────────────
        sparql = f"""
        SELECT ?person ?personLabel ?personDescription
               (YEAR(?date) as ?year) ?affiliationLabel
        WHERE {{
          ?person p:P166 ?awardStatement .
          ?awardStatement ps:P166 wd:{prize_qid} .
          OPTIONAL {{ ?awardStatement pq:P585 ?date }}
          OPTIONAL {{
            ?awardStatement pq:P108 ?affiliation .
          }}
          {year_filter}
          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en,es".
          }}
        }}
        ORDER BY DESC(?year)
        LIMIT {limit}
        """
        # Note: Double braces {{ }} because of f-string escaping

        # ─────────────────────────────────────────────────────────────────────
        # Execute query and parse results
        # ─────────────────────────────────────────────────────────────────────
        results = await self._query(sparql)

        entities = []
        for r in results:
            # Extract Q-ID from full URI
            qid = r.get("person", {}).get("value", "").split("/")[-1]
            # "http://www.wikidata.org/entity/Q937" → "Q937"

            # Get label (name)
            label = r.get("personLabel", {}).get("value", "Unknown")

            # Get description if available
            description = r.get("personDescription", {}).get("value")

            # Get year as string (may be empty)
            year_str = r.get("year", {}).get("value")

            # Get affiliation if available
            affiliation = r.get("affiliationLabel", {}).get("value")

            # Build entity
            entity = WikidataEntity(
                qid=qid,
                label=label,
                description=description,
                award_date=datetime(int(year_str), 1, 1) if year_str else None,
                # Convert year to January 1st of that year
                award_id=prize_qid,
                affiliation=affiliation,
            )
            entities.append(entity)

        return entities

    # =========================================================================
    # CONVENIENCE METHODS: SPECIFIC PRIZES
    # =========================================================================

    async def get_fields_medal_winners(
        self,
        year: Optional[int] = None,
    ) -> list[WikidataEntity]:
        """
        Get Fields Medal winners.

        The Fields Medal is the highest honor in mathematics, often called
        the "Nobel Prize of Mathematics" (though Nobel has no math prize).

        Args:
            year: Filter by award year (awarded every 4 years: 2022, 2018, 2014...)

        Returns:
            List of Fields Medal winners

        Historical Note:
        ────────────────
        - First awarded: 1936
        - Given every 4 years at ICM (International Congress of Mathematicians)
        - Recipients must be under 40 years old
        - 2-4 winners per cycle
        """
        return await self.get_prize_winners(
            self.PRIZE_IDS["fields_medal"],
            year=year,
        )

    async def get_turing_award_winners(
        self,
        year: Optional[int] = None,
    ) -> list[WikidataEntity]:
        """
        Get ACM A.M. Turing Award winners.

        The Turing Award is the highest honor in computer science,
        often called the "Nobel Prize of Computing."

        Args:
            year: Filter by award year

        Returns:
            List of Turing Award winners

        Historical Note:
        ────────────────
        - Named after Alan Turing
        - First awarded: 1966
        - Awarded annually by ACM
        - Currently $1 million prize (funded by Google)
        """
        return await self.get_prize_winners(
            self.PRIZE_IDS["turing_award"],
            year=year,
        )

    async def get_abel_prize_winners(
        self,
        year: Optional[int] = None,
    ) -> list[WikidataEntity]:
        """
        Get Abel Prize winners.

        The Abel Prize is a mathematics prize without age restriction,
        complementing the Fields Medal.

        Args:
            year: Filter by award year

        Returns:
            List of Abel Prize winners

        Historical Note:
        ────────────────
        - Named after Niels Henrik Abel
        - First awarded: 2003
        - Awarded annually by Norwegian Academy of Science and Letters
        - Currently ~$700,000 prize
        """
        return await self.get_prize_winners(
            self.PRIZE_IDS["abel_prize"],
            year=year,
        )

    async def get_breakthrough_prize_winners(
        self,
        category: str = "math",
        year: Optional[int] = None,
    ) -> list[WikidataEntity]:
        """
        Get Breakthrough Prize winners.

        The Breakthrough Prizes are funded by tech billionaires
        (Zuckerberg, Milner, Brin, etc.) and are the world's largest
        science prizes ($3 million each).

        Args:
            category: Prize category (math, physics, life)
            year: Filter by year

        Returns:
            List of Breakthrough Prize winners

        Raises:
            ValueError: If unknown category

        Categories:
        ───────────
        - math: Mathematics
        - physics: Fundamental Physics
        - life: Life Sciences
        """
        prize_key = f"breakthrough_{category}"
        qid = self.PRIZE_IDS.get(prize_key)

        if not qid:
            raise ValueError(f"Unknown Breakthrough Prize category: {category}")

        return await self.get_prize_winners(qid, year=year)

    async def get_wolf_prize_winners(
        self,
        category: str = "math",
        year: Optional[int] = None,
    ) -> list[WikidataEntity]:
        """
        Get Wolf Prize winners.

        The Wolf Prize is awarded by the Wolf Foundation in Israel,
        often seen as a predictor for Nobel Prizes.

        Args:
            category: Prize category (math, physics, chemistry)
            year: Filter by year

        Returns:
            List of Wolf Prize winners

        Raises:
            ValueError: If unknown category
        """
        prize_key = f"wolf_prize_{category}"
        qid = self.PRIZE_IDS.get(prize_key)

        if not qid:
            raise ValueError(f"Unknown Wolf Prize category: {category}")

        return await self.get_prize_winners(qid, year=year)

    # =========================================================================
    # PUBLIC API: SEARCH SCIENTIST
    # =========================================================================

    async def search_scientist(self, name: str) -> list[WikidataEntity]:
        """
        Search for a scientist by name.

        Args:
            name: Scientist name to search (case-insensitive, partial match)

        Returns:
            List of matching scientist entities

        Example:
        ────────
        scientists = await client.search_scientist("Feynman")
        for s in scientists:
            print(f"{s.qid}: {s.label} - {s.description}")
        # Q39246: Richard Feynman - American theoretical physicist

        SPARQL Query:
        ─────────────
        This query:
        1. Finds humans (Q5)
        2. Who have occupation that's a subclass of scientist (Q901)
        3. Whose name contains the search term

        Note: This is a simplified search. For production, consider
        using Wikidata's MediaWiki API for better text search.
        """
        sparql = f"""
        SELECT ?person ?personLabel ?personDescription WHERE {{
          ?person wdt:P31 wd:Q5 .        # Instance of human
          ?person wdt:P106 ?occupation . # Has occupation
          ?occupation wdt:P279* wd:Q901 . # Occupation is scientist or subclass
          ?person rdfs:label ?label .
          FILTER(CONTAINS(LCASE(?label), LCASE("{name}")))
          FILTER(LANG(?label) = "en")
          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        LIMIT 20
        """
        # P31 = instance of
        # P106 = occupation
        # P279* = subclass of (transitive)
        # Q5 = human
        # Q901 = scientist

        results = await self._query(sparql)

        return [
            WikidataEntity(
                qid=r.get("person", {}).get("value", "").split("/")[-1],
                label=r.get("personLabel", {}).get("value", "Unknown"),
                description=r.get("personDescription", {}).get("value"),
            )
            for r in results
        ]

    # =========================================================================
    # PUBLIC API: GET SCIENTIST'S PRIZES
    # =========================================================================

    async def get_scientist_prizes(self, qid: str) -> list[dict[str, Any]]:
        """
        Get all prizes won by a scientist.

        Args:
            qid: Wikidata Q-ID of the scientist (e.g., "Q937" for Einstein)

        Returns:
            List of prize records with award name and year

        Example:
        ────────
        # Get all of Einstein's awards
        prizes = await client.get_scientist_prizes("Q937")
        for p in prizes:
            print(f"{p['year']}: {p['award_name']}")

        # Output includes:
        # 1921: Nobel Prize in Physics
        # 1926: Royal Society Medal
        # 1929: Max Planck Medal
        # ... and many more

        Finding Q-IDs:
        ──────────────
        Use search_scientist() first, then use the Q-ID:

        scientists = await client.search_scientist("Einstein")
        einstein = scientists[0]  # Q937
        prizes = await client.get_scientist_prizes(einstein.qid)
        """
        sparql = f"""
        SELECT ?award ?awardLabel (YEAR(?date) as ?year) WHERE {{
          wd:{qid} p:P166 ?awardStatement .  # Subject's award statements
          ?awardStatement ps:P166 ?award .    # The award itself
          OPTIONAL {{ ?awardStatement pq:P585 ?date }}  # Award date
          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
          }}
        }}
        ORDER BY ?year
        """

        results = await self._query(sparql)

        return [
            {
                "award_qid": r.get("award", {}).get("value", "").split("/")[-1],
                "award_name": r.get("awardLabel", {}).get("value"),
                "year": r.get("year", {}).get("value"),
            }
            for r in results
        ]


# =============================================================================
#                          USAGE EXAMPLES
# =============================================================================
#
# Example 1: Get recent Fields Medal winners
# ──────────────────────────────────────────
# async def recent_fields():
#     client = WikidataClient()
#     try:
#         # Get 2022 Fields Medal winners
#         winners = await client.get_fields_medal_winners(year=2022)
#         print("2022 Fields Medal Winners:")
#         for w in winners:
#             print(f"  {w.label}: {w.description}")
#             if w.affiliation:
#                 print(f"    Affiliation: {w.affiliation}")
#     finally:
#         await client.close()
#
# Example 2: Compare Turing Award and Fields Medal winners
# ────────────────────────────────────────────────────────
# async def compare_prizes():
#     async with WikidataClient() as client:
#         turing = await client.get_turing_award_winners()
#         fields = await client.get_fields_medal_winners()
#
#         # Find any overlap (rare!)
#         turing_qids = {w.qid for w in turing}
#         overlap = [w for w in fields if w.qid in turing_qids]
#         print(f"Scientists with both Turing and Fields: {len(overlap)}")
#
# Example 3: Track scientist's career awards
# ──────────────────────────────────────────
# async def scientist_awards():
#     client = WikidataClient()
#     try:
#         # Search for scientist
#         scientists = await client.search_scientist("Terence Tao")
#         if scientists:
#             tao = scientists[0]
#             print(f"Found: {tao.label} ({tao.qid})")
#
#             # Get all their awards
#             prizes = await client.get_scientist_prizes(tao.qid)
#             print(f"\nAwards ({len(prizes)} total):")
#             for p in prizes:
#                 year = p.get('year', 'Unknown year')
#                 print(f"  {year}: {p['award_name']}")
#     finally:
#         await client.close()
# =============================================================================
