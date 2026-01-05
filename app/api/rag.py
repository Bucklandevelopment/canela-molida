"""
===============================================================================
                    RAG API ROUTER - DOCUMENTATION
===============================================================================

Module: app/api/rag.py
Purpose: REST API endpoints for Retrieval-Augmented Generation queries

===============================================================================
                         ROUTER OVERVIEW
===============================================================================

This router provides the core RAG functionality - asking questions about
your scientific paper collection:

┌─────────────────────────────────────────────────────────────────────────────┐
│                           RAG ROUTER ENDPOINTS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   QUERY ENDPOINTS                                                           │
│   ───────────────                                                           │
│   POST /rag/query        Full RAG: answer + sources (JSON)                 │
│   POST /rag/query/stream Full RAG with streaming (SSE)                     │
│   GET  /rag/ask          Simple query via GET                              │
│                                                                             │
│   SEARCH ENDPOINTS                                                          │
│   ────────────────                                                          │
│   GET /rag/search        Search without generation                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

===============================================================================
                    RAG PIPELINE VISUALIZATION
===============================================================================

                         User Question
                              │
                              ▼
           ┌──────────────────────────────────────┐
           │         SEMANTIC CACHE CHECK         │
           │      Similarity > 0.95 → Cache Hit   │
           │           (65x speedup)              │
           └───────────────┬──────────────────────┘
                           │
              Cache Miss   │   Cache Hit
                   ↓       └────────────────────────────┐
                   │                                    │
                   ▼                                    │
           ┌──────────────────────────────────────┐     │
           │        EMBED QUERY (BGE-M3)          │     │
           │     1024-dim multilingual vector     │     │
           └───────────────┬──────────────────────┘     │
                           │                            │
                           ▼                            │
           ┌──────────────────────────────────────┐     │
           │     VECTOR SEARCH (LanceDB)          │     │
           │   IVF-PQ index → top_k chunks        │     │
           └───────────────┬──────────────────────┘     │
                           │                            │
                           ▼                            │
           ┌──────────────────────────────────────┐     │
           │      CONTEXT ASSEMBLY                │     │
           │   [CONTEXT 1: {title}]               │     │
           │   {chunk_text}                       │     │
           │   ...                                │     │
           └───────────────┬──────────────────────┘     │
                           │                            │
                           ▼                            │
           ┌──────────────────────────────────────┐     │
           │       LLM GENERATION (Ollama)        │     │
           │       Llama 3.1 8B / Qwen2 7B        │     │
           └───────────────┬──────────────────────┘     │
                           │                            │
                           ▼                            ▼
                    ┌─────────────────────────────────────┐
                    │           RAGResponse               │
                    │   - answer: str                     │
                    │   - sources: List[RetrievedContext] │
                    │   - cached: bool                    │
                    └─────────────────────────────────────┘

===============================================================================
                    STREAMING vs NON-STREAMING
===============================================================================

┌──────────────┬────────────────────────────────────────────────────────────┐
│ POST /query  │ Non-streaming (JSON)                                       │
│              │ - Waits for complete response                              │
│              │ - Returns full JSON object                                 │
│              │ - Best for: APIs, batch processing                         │
│              │ - Latency: 2-5 seconds (full generation)                   │
├──────────────┼────────────────────────────────────────────────────────────┤
│ POST /query/ │ Streaming (SSE)                                            │
│ stream       │ - Returns tokens as generated                              │
│              │ - Server-Sent Events format                                │
│              │ - Best for: Chat UI, real-time display                     │
│              │ - Time to first token: ~300ms                              │
└──────────────┴────────────────────────────────────────────────────────────┘

Server-Sent Events (SSE) Format:
────────────────────────────────
```
data: The

data: transformer

data: architecture

data: uses

data: self-attention

data: [DONE]
```

Each line is a chunk of the response. The [DONE] sentinel signals completion.

===============================================================================
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from typing import Optional
# Optional: Type hint for values that can be None

# =============================================================================
# THIRD-PARTY IMPORTS: FastAPI
# =============================================================================

from fastapi import APIRouter, Query
# APIRouter: FastAPI router for organizing endpoints
# Query: Validate and document query parameters

from fastapi.responses import StreamingResponse
# StreamingResponse: Return data as a stream
# Used for: Server-Sent Events (SSE), file downloads
#
# StreamingResponse takes an async generator and streams chunks
# to the client as they become available

# =============================================================================
# LOCAL IMPORTS
# =============================================================================

from app.models.rag import RAGQuery, RAGResponse
# RAGQuery: Pydantic model for query requests
#   - question: str
#   - top_k: int (default 10)
#   - year_min/max: Optional[int]
#   - use_semantic_cache: bool (default True)
#
# RAGResponse: Pydantic model for query responses
#   - answer: str (LLM-generated response)
#   - sources: List[RetrievedContext]
#   - cached: bool (was this from cache?)

from app.services.rag import get_rag_service
# get_rag_service(): Singleton RAG service
# Uses @lru_cache to ensure single instance
# Handles: embedding, retrieval, generation, caching

# =============================================================================
# ROUTER CONFIGURATION
# =============================================================================

router = APIRouter(
    prefix="/rag",
    # prefix: All routes start with /rag
    # Full path: /api/rag/... (after main.py adds /api)

    tags=["rag"],
    # tags: Groups endpoints in OpenAPI docs under "rag"
)


# =============================================================================
# ENDPOINT: RAG QUERY (NON-STREAMING)
# =============================================================================

@router.post("/query", response_model=RAGResponse)
async def rag_query(request: RAGQuery) -> RAGResponse:
    """
    Execute RAG query and return answer with sources.

    Pipeline:
    1. Check semantic cache (0.95 threshold for 65x speedup)
    2. Embed query with BGE-M3
    3. Retrieve from LanceDB
    4. Generate with Ollama (Llama 3.1 8B)
    5. Cache response

    This is the primary endpoint for question-answering. It:
    - Retrieves relevant paper chunks from the vector store
    - Uses an LLM to synthesize an answer
    - Returns citations to source papers

    Request Body (RAGQuery):
    ────────────────────────
    ```json
    {
      "question": "What is the attention mechanism?",
      "top_k": 10,           // Number of chunks to retrieve
      "year_min": 2020,      // Optional: Filter papers by year
      "year_max": 2024,      // Optional: Filter papers by year
      "use_semantic_cache": true  // Use cache for similar questions
    }
    ```

    Response (RAGResponse):
    ───────────────────────
    ```json
    {
      "answer": "The attention mechanism is a neural network component...",
      "sources": [
        {
          "chunk_id": "paper123_chunk_5",
          "paper_id": "paper123",
          "title": "Attention Is All You Need",
          "authors": ["Vaswani et al."],
          "year": 2017,
          "text": "The dominant sequence transduction models...",
          "score": 0.89
        }
      ],
      "cached": false,
      "query": "What is the attention mechanism?"
    }
    ```

    Performance:
    ────────────
    - Cache hit: ~50ms (65x faster)
    - Cache miss: 2-5s (embedding + retrieval + generation)

    Semantic Cache:
    ───────────────
    The system caches responses keyed by query embeddings.
    Similar questions (cosine similarity > 0.95) return cached answers.
    Example cache hits:
    - "What is attention?" → cached
    - "What is the attention mechanism?" → same answer
    - "Explain attention in transformers" → same answer
    """
    # ─────────────────────────────────────────────────────────────────────────
    # Get singleton RAG service
    # ─────────────────────────────────────────────────────────────────────────
    service = get_rag_service()
    # Singleton ensures:
    # - Same LanceDB connection
    # - Shared embedding cache
    # - Shared semantic cache

    # ─────────────────────────────────────────────────────────────────────────
    # Execute RAG pipeline
    # ─────────────────────────────────────────────────────────────────────────
    return await service.query(request)
    # query() handles:
    # 1. Semantic cache check
    # 2. Query embedding (BGE-M3)
    # 3. Vector search (LanceDB)
    # 4. Context assembly
    # 5. LLM generation (Ollama)
    # 6. Response caching


# =============================================================================
# ENDPOINT: RAG QUERY (STREAMING)
# =============================================================================

@router.post("/query/stream")
async def rag_query_stream(request: RAGQuery) -> StreamingResponse:
    """
    Execute RAG query with streaming response.

    Returns Server-Sent Events for real-time display.

    This endpoint streams the LLM response token-by-token, enabling
    real-time display in chat interfaces. The pipeline is:
    1. Same retrieval as /query
    2. Stream LLM tokens as they're generated
    3. End with [DONE] sentinel

    Request Body (RAGQuery):
    ────────────────────────
    Same as /query endpoint.

    Response (text/event-stream):
    ─────────────────────────────
    ```
    data: The

    data: transformer

    data: architecture

    data: revolutionized

    data: natural

    data: language

    data: processing

    data: [DONE]
    ```

    Why SSE?
    ────────
    Server-Sent Events (SSE) is simpler than WebSockets for unidirectional
    streaming:
    - Standard HTTP (no upgrade handshake)
    - Automatic reconnection
    - Works through proxies
    - Browser EventSource API

    JavaScript Client Example:
    ──────────────────────────
    ```javascript
    const eventSource = new EventSource('/api/rag/query/stream', {
      method: 'POST',
      body: JSON.stringify({ question: "What is attention?" }),
      headers: { 'Content-Type': 'application/json' }
    });

    eventSource.onmessage = (event) => {
      if (event.data === '[DONE]') {
        eventSource.close();
        return;
      }
      // Append token to display
      outputElement.textContent += event.data;
    };
    ```

    Note: Standard EventSource only supports GET. For POST with SSE,
    use fetch() with ReadableStream or a library like eventsource-polyfill.

    Python Client Example:
    ──────────────────────
    ```python
    import httpx

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:3690/api/rag/query/stream",
            json={"question": "What is attention?"}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    token = line[6:]  # Strip "data: " prefix
                    if token == "[DONE]":
                        break
                    print(token, end="", flush=True)
    ```
    """
    service = get_rag_service()

    # ─────────────────────────────────────────────────────────────────────────
    # Define async generator for streaming
    # ─────────────────────────────────────────────────────────────────────────
    async def generate():
        """
        Async generator that yields SSE-formatted chunks.

        SSE Format:
        - Each message is: "data: {content}\n\n"
        - Double newline separates messages
        - [DONE] signals stream end
        """
        async for chunk in service.query_stream(request):
            # query_stream yields individual tokens from LLM
            yield f"data: {chunk}\n\n"
            # Format: "data: {token}\n\n"
            # The double newline is SSE message separator

        yield "data: [DONE]\n\n"
        # Sentinel to signal completion
        # Client should close connection on receiving this

    # ─────────────────────────────────────────────────────────────────────────
    # Return streaming response
    # ─────────────────────────────────────────────────────────────────────────
    return StreamingResponse(
        generate(),
        # The async generator function

        media_type="text/event-stream",
        # MIME type for Server-Sent Events
        # Tells client to expect SSE format
    )


# =============================================================================
# ENDPOINT: SEARCH WITHOUT GENERATION
# =============================================================================

@router.get("/search")
async def search_papers(
    query: str,
    # query: Required search terms

    top_k: int = Query(default=10, ge=1, le=100),
    # top_k: Number of chunks to return (max 100)

    year_min: Optional[int] = None,
    # year_min: Minimum publication year filter

    year_max: Optional[int] = None,
    # year_max: Maximum publication year filter
) -> list[dict]:
    """
    Search for relevant paper chunks without generating an answer.

    Useful for exploring the knowledge base.

    This endpoint performs only the retrieval step of RAG:
    - Embeds the query
    - Searches the vector store
    - Returns matching chunks with metadata

    No LLM generation = much faster (~100ms vs 2-5s).

    Use Cases:
    ──────────
    - Exploring what's in the database
    - Finding specific papers
    - Debugging retrieval quality
    - Building custom UIs

    Request Parameters:
    ───────────────────
    - query (required): Search terms
    - top_k (default 10): Number of results (max 100)
    - year_min (optional): Filter by minimum year
    - year_max (optional): Filter by maximum year

    Response:
    ─────────
    List of chunk objects:
    ```json
    [
      {
        "chunk_id": "2301.08422_chunk_3",
        "paper_id": "2301.08422",
        "title": "Paper Title",
        "authors": ["Author 1", "Author 2"],
        "year": 2023,
        "text": "Relevant text from the paper...",
        "score": 0.92
      }
    ]
    ```

    Score Interpretation:
    ─────────────────────
    - 0.90+: Very relevant (direct match)
    - 0.80-0.90: Relevant (related concept)
    - 0.70-0.80: Somewhat relevant
    - <0.70: May not be relevant

    Example:
    ────────
    GET /api/rag/search?query=attention+mechanism&top_k=5&year_min=2020
    """
    service = get_rag_service()

    return service.search_papers(
        query=query,
        top_k=top_k,
        year_min=year_min,
        year_max=year_max,
    )
    # search_papers() does:
    # 1. Embed query with BGE-M3
    # 2. Search LanceDB with filters
    # 3. Return chunks with scores (no LLM)


# =============================================================================
# ENDPOINT: SIMPLE GET QUERY
# =============================================================================

@router.get("/ask")
async def ask_question(
    question: str,
    # question: The question to answer

    top_k: int = Query(default=10, ge=1, le=50),
    # top_k: Chunks to retrieve (lower max for GET)

    year_min: Optional[int] = None,
    # year_min: Minimum publication year

    year_max: Optional[int] = None,
    # year_max: Maximum publication year

    use_cache: bool = True,
    # use_cache: Whether to use semantic cache
) -> RAGResponse:
    """
    Simple GET endpoint for asking questions.

    Convenience wrapper around POST /query.

    Sometimes you want to ask a question via URL without constructing
    a POST body. This endpoint allows that:

    GET /api/rag/ask?question=What+is+attention?

    vs

    POST /api/rag/query
    {"question": "What is attention?"}

    Both produce the same result.

    Request Parameters:
    ───────────────────
    - question (required): The question to ask
    - top_k (default 10): Number of chunks (max 50 for GET)
    - year_min/max (optional): Year filters
    - use_cache (default true): Use semantic cache

    Response:
    ─────────
    Same as POST /query (RAGResponse object).

    URL Encoding:
    ─────────────
    Remember to URL-encode spaces and special characters:
    - Space: %20 or +
    - ?: %3F
    - &: %26

    Example:
    ────────
    GET /api/rag/ask?question=What+is+the+attention+mechanism%3F&top_k=5

    Use Cases:
    ──────────
    - Browser testing (paste URL)
    - Simple integrations (curl one-liner)
    - Debugging

    For production applications, prefer POST /query:
    - Larger question limit (URL length limits)
    - Cleaner handling of special characters
    - Standard REST semantics (queries that have side effects)
    """
    # ─────────────────────────────────────────────────────────────────────────
    # Build RAGQuery from parameters
    # ─────────────────────────────────────────────────────────────────────────
    request = RAGQuery(
        question=question,
        top_k=top_k,
        year_min=year_min,
        year_max=year_max,
        use_semantic_cache=use_cache,
    )
    # Convert GET params to same model used by POST

    # ─────────────────────────────────────────────────────────────────────────
    # Execute same pipeline as POST /query
    # ─────────────────────────────────────────────────────────────────────────
    service = get_rag_service()
    return await service.query(request)
    # Identical processing to POST /query


# =============================================================================
#                         USAGE NOTES
# =============================================================================
#
# CHOOSING THE RIGHT ENDPOINT:
# ────────────────────────────
# 1. POST /query → Production apps, full RAG with JSON response
# 2. POST /query/stream → Chat UIs, real-time token display
# 3. GET /search → Exploration, retrieval-only, debugging
# 4. GET /ask → Quick testing, browser debugging
#
# PERFORMANCE OPTIMIZATION:
# ─────────────────────────
# - Enable semantic cache for 65x speedup on similar queries
# - Adjust top_k based on use case (more chunks = slower but more context)
# - Use year filters to reduce search space
#
# ERROR HANDLING:
# ───────────────
# - Empty results: Query doesn't match any indexed papers
# - Timeout: Ollama not running or overloaded
# - 500 errors: Check Ollama, LanceDB connectivity
# =============================================================================
