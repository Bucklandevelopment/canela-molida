# =============================================================================
# Canela-Molida (Scientific Library RAG) - Dockerfile
# FastAPI + LanceDB + BGE-M3 + Ollama
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder - install dependencies in a throwaway layer
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime - lean production image
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Install runtime-only system dependencies
#   curl  - health check probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application source
COPY app/ ./app/
COPY pyproject.toml .
COPY taxonomy/ ./taxonomy/

# Create data directories that the app expects
RUN mkdir -p data/pdfs data/markdown data/vectors metadata .cache

# Create non-root user and give ownership of writable dirs
RUN useradd -r -s /bin/false appuser \
    && chown -R appuser:appuser /app

USER appuser

# canela-molida listens on port 3690
EXPOSE 3690

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3690/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3690"]
