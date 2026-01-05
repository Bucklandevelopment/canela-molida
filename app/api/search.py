"""
===============================================================================
                    SEARCH API ROUTER - DOCUMENTATION
===============================================================================

Module: app/api/search.py
Purpose: REST API endpoints for searching papers and scientific prizes

===============================================================================
                         ROUTER OVERVIEW
===============================================================================

This router provides search functionality across multiple domains:

┌─────────────────────────────────────────────────────────────────────────────┐
│                         SEARCH ROUTER ENDPOINTS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   LOCAL SEARCH                                                              │
│   ────────────                                                              │
│   GET /search/papers           Vector search in indexed papers             │
│                                                                             │
│   NOBEL PRIZES (Official API)                                              │
│   ────────────────────────────                                              │
│   GET /search/nobel            Nobel Prize laureates (1901-present)        │
│                                                                             │
│   OTHER PRIZES (Wikidata SPARQL)                                           │
│   ──────────────────────────────                                            │
│   GET /search/fields-medal     Fields Medal (Mathematics)                  │
│   GET /search/turing-award     Turing Award (Computing)                    │
│   GET /search/abel-prize       Abel Prize (Mathematics)                    │
│   GET /search/prizes/{qid}     Any prize by Wikidata Q-ID                 │
│                                                                             │
│   SCIENTIST LOOKUP                                                          │
│   ────────────────                                                          │
│   GET /search/scientist/{qid}/prizes  All prizes for a scientist          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                    SEARCH SOURCES COMPARISON
===============================================================================

┌────────────────┬────────────────────────────────────────────────────────────┐
│ /search/papers │ LOCAL VECTOR STORE                                        │
│                │ - Searches YOUR indexed papers                            │
│                │ - Semantic similarity (not keyword)                       │
│                │ - Filtered by year, metadata                              │
│                │ - ~100ms latency                                          │
├────────────────┼────────────────────────────────────────────────────────────┤
│ /search/nobel  │ NOBEL PRIZE API                                           │
│                │ - Official data since 1901                                │
│                │ - 6 categories, ~960 laureates                            │
│                │ - Complete and authoritative                              │
│                │ - No rate limit                                           │
├────────────────┼────────────────────────────────────────────────────────────┤
│ /search/       │ WIKIDATA SPARQL                                           │
│ fields-medal   │ - Community-maintained data                               │
│ turing-award   │ - Fields Medal, Turing, Abel, etc.                        │
│ abel-prize     │ - ~1-10s latency (complex queries)                        │
│ prizes/{qid}   │ - Any prize by Wikidata Q-ID                              │
└────────────────┴────────────────────────────────────────────────────────────┘

===============================================================================
                    MAJOR SCIENTIFIC PRIZES
===============================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRIZE QUICK REFERENCE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   PHYSICS                           MATHEMATICS                             │
│   ───────                           ───────────                             │
│   Nobel Prize (1901-)               Fields Medal (1936-, Q28835)           │
│   Wolf Prize (1978-, Q694251)       Abel Prize (2003-, Q160042)            │
│   Breakthrough Prize (2012-)        Wolf Prize (1978-, Q194351)            │
│                                                                             │
│   COMPUTER SCIENCE                  LIFE SCIENCES                          │
│   ────────────────                  ─────────────                          │
│   Turing Award (1966-, Q185667)     Nobel Prize (Medicine)                 │
│   Breakthrough Prize (CS)           Lasker Award (Q645891, Q645892)        │
│                                     Breakthrough Prize (Life)               │
│                                                                             │
│   CHEMISTRY                         GENERAL                                 │
│   ─────────                         ───────                                 │
│   Nobel Prize (1901-)               Kavli Prizes (3 fields)                │
│   Wolf Prize (1978-, Q852298)       Shaw Prizes (3 fields)                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from typing import Optional, Any
# Optional: Type hint for values that can be None
# Any: Type hint for dynamic types

# =============================================================================
# THIRD-PARTY IMPORTS: FastAPI
# =============================================================================

from fastapi import APIRouter, Query
# APIRouter: FastAPI router for organizing endpoints
# Query: Validate and document query parameters

# =============================================================================
# LOCAL IMPORTS
# =============================================================================

from app.services.apis import NobelClient, WikidataClient
# NobelClient: Official Nobel Prize API client
# WikidataClient: SPARQL client for other prizes

from app.services.vectorstore import get_vectorstore_service
# get_vectorstore_service(): Singleton vector store service
# Handles: LanceDB operations, semantic search

# =============================================================================
# ROUTER CONFIGURATION
# =============================================================================

router = APIRouter(
    prefix="/search",
    # prefix: All routes start with /search
    # Full path: /api/search/...

    tags=["search"],
    # tags: Groups endpoints in OpenAPI docs under "search"
)


# =============================================================================
# ENDPOINT: SEARCH LOCAL PAPERS
# =============================================================================

@router.get("/papers")
async def search_papers(
    query: str,
    # query: Search terms (semantic, not keyword)

    top_k: int = Query(default=10, ge=1, le=100),
    # top_k: Number of results (max 100)

    year_min: Optional[int] = None,
    # year_min: Minimum publication year

    year_max: Optional[int] = None,
    # year_max: Maximum publication year
) -> dict:
    """
    Search indexed papers in the vector store.

    This endpoint performs semantic search over your locally indexed
    papers. Unlike keyword search, it understands meaning:
    - "neural network training" matches "deep learning optimization"
    - "attention mechanism" matches "self-attention transformer"

    Request Parameters:
    ───────────────────
    - query (required): Search terms
    - top_k (default 10): Number of results (max 100)
    - year_min (optional): Filter by minimum year
    - year_max (optional): Filter by maximum year

    Response:
    ─────────
    ```json
    {
      "query": "attention mechanism",
      "count": 10,
      "results": [
        {
          "chunk_id": "2301.08422_chunk_3",
          "paper_id": "2301.08422",
          "title": "Paper Title",
          "authors": ["Author 1"],
          "year": 2023,
          "text": "The attention mechanism...",
          "score": 0.92
        }
      ]
    }
    ```

    Score Interpretation:
    ─────────────────────
    - 0.90+: Highly relevant
    - 0.80-0.90: Relevant
    - 0.70-0.80: Somewhat relevant
    - <0.70: May not be relevant

    Example:
    ────────
    GET /api/search/papers?query=transformer+attention&top_k=5&year_min=2020
    """
    vectorstore = get_vectorstore_service()

    results = vectorstore.search(
        query=query,
        top_k=top_k,
        year_min=year_min,
        year_max=year_max,
    )
    # search() does:
    # 1. Embed query with BGE-M3
    # 2. Vector search in LanceDB
    # 3. Apply year filters
    # 4. Return chunks with scores

    return {
        "query": query,
        "count": len(results),
        "results": results,
    }


# =============================================================================
# ENDPOINT: SEARCH NOBEL LAUREATES
# =============================================================================

@router.get("/nobel")
async def search_nobel_laureates(
    category: Optional[str] = None,
    # category: Prize category
    # Options: physics, chemistry, medicine, literature, peace, economics

    year: Optional[int] = None,
    # year: Exact award year (overrides year_from)

    year_from: Optional[int] = None,
    # year_from: Minimum award year

    year_to: Optional[int] = None,
    # year_to: Maximum award year

    limit: int = Query(default=50, ge=1, le=200),
    # limit: Maximum results (Nobel has ~960 total)
) -> dict:
    """
    Search Nobel Prize laureates.

    Nobel API: api.nobelprize.org, complete data since 1901.

    Categories: physics, chemistry, medicine, literature, peace, economics

    This endpoint queries the official Nobel Prize API, providing
    authoritative data on all Nobel laureates.

    Request Parameters:
    ───────────────────
    - category (optional): physics, chemistry, medicine, literature, peace, economics
    - year (optional): Exact year (e.g., 2023)
    - year_from (optional): Minimum year (e.g., 2020)
    - year_to (optional): Maximum year (e.g., 2023)
    - limit (default 50): Maximum results

    Response:
    ─────────
    ```json
    {
      "count": 3,
      "laureates": [
        {
          "id": "1012",
          "name": "Pierre Agostini",
          "prizes": [
            {
              "category": "Physics",
              "year": "2023",
              "motivation": "for experimental methods..."
            }
          ]
        }
      ]
    }
    ```

    Category Codes:
    ───────────────
    - physics (phy)
    - chemistry (che)
    - medicine (med) / physiology
    - literature (lit)
    - peace (pea)
    - economics (eco)

    Historical Notes:
    ─────────────────
    - First prizes: 1901
    - Economics added: 1969
    - Some years have no prize (wars, no worthy candidate)
    - 1-3 people can share a prize

    Example:
    ────────
    GET /api/search/nobel?category=physics&year_from=2020
    """
    client = NobelClient()

    try:
        laureates = await client.get_laureates(
            category=category,
            year_from=year or year_from,  # year overrides year_from
            year_to=year_to,
            limit=limit,
        )

        # ─────────────────────────────────────────────────────────────────────
        # Format response
        # ─────────────────────────────────────────────────────────────────────
        return {
            "count": len(laureates),
            "laureates": [
                {
                    "id": l.id,
                    "name": l.get_name(),
                    # get_name() extracts from nested knownName structure

                    "prizes": [
                        {
                            "category": p.get("category", {}).get("en"),
                            # Category in English

                            "year": p.get("awardYear"),
                            # Award year as string

                            "motivation": p.get("motivation", {}).get("en"),
                            # Prize motivation in English
                        }
                        for p in l.nobelPrizes
                        # Each laureate may have multiple prizes
                        # (4 people have won twice)
                    ],
                }
                for l in laureates
            ],
        }

    finally:
        await client.close()


# =============================================================================
# ENDPOINT: SEARCH FIELDS MEDAL
# =============================================================================

@router.get("/fields-medal")
async def search_fields_medal(
    year: Optional[int] = None,
    # year: Award year (given every 4 years: 2022, 2018, 2014, ...)
) -> dict:
    """
    Get Fields Medal winners from Wikidata.

    Fields Medal (Q28835): Mathematics, awarded every 4 years since 1936.

    The Fields Medal is often called the "Nobel Prize of Mathematics"
    (Nobel has no mathematics prize). It's awarded to 2-4 mathematicians
    under 40 at the International Congress of Mathematicians.

    Request Parameters:
    ───────────────────
    - year (optional): Award year (e.g., 2022)

    Response:
    ─────────
    ```json
    {
      "prize": "Fields Medal",
      "count": 4,
      "winners": [
        {
          "qid": "Q28835xxx",
          "name": "June Huh",
          "year": 2022,
          "affiliation": "Princeton University"
        }
      ]
    }
    ```

    Award Years:
    ────────────
    Awarded every 4 years: 2022, 2018, 2014, 2010, ...
    (Skipped 1936-1950 due to WWII)

    Notable Winners:
    ────────────────
    - John von Neumann (declined, over 40)
    - Terence Tao (2006)
    - Maryam Mirzakhani (2014, first woman)

    Example:
    ────────
    GET /api/search/fields-medal?year=2022
    """
    client = WikidataClient()

    try:
        winners = await client.get_fields_medal_winners(year=year)

        return {
            "prize": "Fields Medal",
            "count": len(winners),
            "winners": [
                {
                    "qid": w.qid,
                    # Wikidata Q-ID for further lookups

                    "name": w.label,
                    # Person's name

                    "year": w.award_date.year if w.award_date else None,
                    # Award year

                    "affiliation": w.affiliation,
                    # Institution at time of award
                }
                for w in winners
            ],
        }

    finally:
        await client.close()


# =============================================================================
# ENDPOINT: SEARCH TURING AWARD
# =============================================================================

@router.get("/turing-award")
async def search_turing_award(
    year: Optional[int] = None,
    # year: Award year (annual since 1966)
) -> dict:
    """
    Get Turing Award winners from Wikidata.

    Turing Award (Q185667): Computing, $1M prize since 1966.

    The ACM A.M. Turing Award is the highest distinction in computer
    science, often called the "Nobel Prize of Computing."

    Request Parameters:
    ───────────────────
    - year (optional): Award year

    Response:
    ─────────
    ```json
    {
      "prize": "Turing Award",
      "count": 1,
      "winners": [
        {
          "qid": "Q185667xxx",
          "name": "Bob Metcalfe",
          "year": 2022,
          "affiliation": "MIT"
        }
      ]
    }
    ```

    Historical Notes:
    ─────────────────
    - Named after Alan Turing
    - First awarded: 1966 (Alan Perlis)
    - $1M prize (funded by Google since 2014)
    - Usually 1 winner per year (sometimes 2-3)

    Notable Winners:
    ────────────────
    - Donald Knuth (1974)
    - Vint Cerf & Bob Kahn (2004, TCP/IP)
    - Geoffrey Hinton, Yann LeCun, Yoshua Bengio (2018, Deep Learning)

    Example:
    ────────
    GET /api/search/turing-award?year=2018
    """
    client = WikidataClient()

    try:
        winners = await client.get_turing_award_winners(year=year)

        return {
            "prize": "Turing Award",
            "count": len(winners),
            "winners": [
                {
                    "qid": w.qid,
                    "name": w.label,
                    "year": w.award_date.year if w.award_date else None,
                    "affiliation": w.affiliation,
                }
                for w in winners
            ],
        }

    finally:
        await client.close()


# =============================================================================
# ENDPOINT: SEARCH ABEL PRIZE
# =============================================================================

@router.get("/abel-prize")
async def search_abel_prize(
    year: Optional[int] = None,
    # year: Award year (annual since 2003)
) -> dict:
    """
    Get Abel Prize winners from Wikidata.

    Abel Prize (Q160042): Mathematics, ~$873K since 2003.

    The Abel Prize complements the Fields Medal by having no age
    restriction. It's awarded by the Norwegian Academy of Science
    and Letters.

    Request Parameters:
    ───────────────────
    - year (optional): Award year

    Response:
    ─────────
    ```json
    {
      "prize": "Abel Prize",
      "count": 1,
      "winners": [
        {
          "qid": "Q160042xxx",
          "name": "Luis Caffarelli",
          "year": 2023,
          "affiliation": "UT Austin"
        }
      ]
    }
    ```

    Historical Notes:
    ─────────────────
    - Named after Niels Henrik Abel (1802-1829)
    - First awarded: 2003 (Jean-Pierre Serre)
    - ~$873,000 prize
    - Usually 1 winner per year

    Example:
    ────────
    GET /api/search/abel-prize?year=2023
    """
    client = WikidataClient()

    try:
        winners = await client.get_abel_prize_winners(year=year)

        return {
            "prize": "Abel Prize",
            "count": len(winners),
            "winners": [
                {
                    "qid": w.qid,
                    "name": w.label,
                    "year": w.award_date.year if w.award_date else None,
                    "affiliation": w.affiliation,
                }
                for w in winners
            ],
        }

    finally:
        await client.close()


# =============================================================================
# ENDPOINT: SEARCH ANY PRIZE BY Q-ID
# =============================================================================

@router.get("/prizes/{prize_qid}")
async def search_prize_by_qid(
    prize_qid: str,
    # prize_qid: Wikidata Q-ID of the prize

    year: Optional[int] = None,
    # year: Filter by award year

    limit: int = Query(default=100, ge=1, le=500),
    # limit: Maximum results
) -> dict:
    """
    Get winners of any prize by Wikidata Q-ID.

    Example Q-IDs:
    - Q28835: Fields Medal
    - Q185667: Turing Award
    - Q160042: Abel Prize
    - Q15046788: Breakthrough Prize (Math)
    - Q194351: Wolf Prize (Math)

    This is a generic endpoint for querying any prize in Wikidata.
    Find Q-IDs by searching Wikidata or using the WikidataClient's
    PRIZE_IDS dictionary.

    Path Parameter:
    ───────────────
    - prize_qid: Wikidata Q-ID of the prize

    Query Parameters:
    ─────────────────
    - year (optional): Filter by award year
    - limit (default 100): Maximum results

    Response:
    ─────────
    ```json
    {
      "prize_qid": "Q28835",
      "count": 60,
      "winners": [
        {
          "qid": "Qxxxxxx",
          "name": "Winner Name",
          "description": "French mathematician",
          "year": 2022,
          "affiliation": "University Name"
        }
      ]
    }
    ```

    Finding Q-IDs:
    ──────────────
    1. Search Wikidata: https://www.wikidata.org/
    2. Look up award page
    3. Q-ID is in the URL: wikidata.org/wiki/Q28835

    Common Q-IDs:
    ─────────────
    - Q28835: Fields Medal
    - Q185667: Turing Award
    - Q160042: Abel Prize
    - Q15046788: Breakthrough Prize (Math)
    - Q16988195: Breakthrough Prize (Physics)
    - Q16988211: Breakthrough Prize (Life Sciences)
    - Q194351: Wolf Prize (Math)
    - Q694251: Wolf Prize (Physics)
    - Q852298: Wolf Prize (Chemistry)

    Example:
    ────────
    GET /api/search/prizes/Q194351?year=2023
    """
    client = WikidataClient()

    try:
        winners = await client.get_prize_winners(
            prize_qid=prize_qid,
            year=year,
            limit=limit,
        )

        return {
            "prize_qid": prize_qid,
            "count": len(winners),
            "winners": [
                {
                    "qid": w.qid,
                    "name": w.label,
                    "description": w.description,
                    # Short description (e.g., "American mathematician")

                    "year": w.award_date.year if w.award_date else None,
                    "affiliation": w.affiliation,
                }
                for w in winners
            ],
        }

    finally:
        await client.close()


# =============================================================================
# ENDPOINT: GET SCIENTIST'S PRIZES
# =============================================================================

@router.get("/scientist/{qid}/prizes")
async def get_scientist_prizes(qid: str) -> dict:
    """
    Get all prizes won by a scientist (by Wikidata Q-ID).

    This endpoint returns all awards/prizes for a given scientist,
    useful for understanding their recognition and impact.

    Path Parameter:
    ───────────────
    - qid: Wikidata Q-ID of the scientist
           Examples: Q937 (Einstein), Q39246 (Feynman)

    Response:
    ─────────
    ```json
    {
      "scientist_qid": "Q937",
      "prizes": [
        {
          "award_qid": "Q38104",
          "award_name": "Nobel Prize in Physics",
          "year": "1921"
        },
        {
          "award_qid": "Q708675",
          "award_name": "Max Planck Medal",
          "year": "1929"
        }
      ]
    }
    ```

    Finding Q-IDs:
    ──────────────
    1. Search Wikidata for the scientist
    2. Q-ID is in the URL

    Some Notable Q-IDs:
    ───────────────────
    - Q937: Albert Einstein
    - Q39246: Richard Feynman
    - Q7186: Marie Curie
    - Q44014: John von Neumann
    - Q727844: Alan Turing

    Example:
    ────────
    GET /api/search/scientist/Q937/prizes
    # Returns all of Einstein's awards
    """
    client = WikidataClient()

    try:
        prizes = await client.get_scientist_prizes(qid)
        # Returns list of {award_qid, award_name, year}

        return {
            "scientist_qid": qid,
            "prizes": prizes,
        }

    finally:
        await client.close()


# =============================================================================
#                         USAGE NOTES
# =============================================================================
#
# CHOOSING THE RIGHT ENDPOINT:
# ────────────────────────────
# - /search/papers → Search YOUR indexed papers
# - /search/nobel → Official Nobel Prize data
# - /search/fields-medal, etc. → Other major prizes via Wikidata
# - /search/prizes/{qid} → Any prize if you know the Q-ID
# - /search/scientist/{qid}/prizes → All prizes for a person
#
# PERFORMANCE:
# ────────────
# - /search/papers: ~100ms (local vector search)
# - /search/nobel: ~500ms (external API)
# - Wikidata endpoints: 1-10s (SPARQL can be slow)
#
# ERROR HANDLING:
# ───────────────
# - Empty results: Valid query but no matches
# - 500: External API error (try again later)
# - Timeout: Wikidata overloaded (increase client timeout)
# =============================================================================
