"""
FastAPI Application Entry Point - Scientific Library RAG.

=============================================================================
                    PUNTO DE ENTRADA DE LA APLICACIÓN
=============================================================================

Este módulo es el "main()" del sistema RAG. Aquí se configura:
1. La aplicación FastAPI con metadatos OpenAPI
2. El ciclo de vida (lifespan) para inicialización/cleanup
3. Middleware CORS para permitir peticiones del frontend
4. Registro de todos los routers de la API

ARQUITECTURA DE UNA APLICACIÓN FASTAPI
======================================

┌─────────────────────────────────────────────────────────────────────────┐
│                         CLIENTE (Browser/Streamlit)                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTP Request
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           MIDDLEWARE STACK                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      CORS Middleware                             │   │
│  │   - Valida Origin headers                                        │   │
│  │   - Añade Access-Control-* headers                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            ROUTING                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │   /                     → root()                                 │   │
│  │   /health               → health()                               │   │
│  │   /stats                → stats()                                │   │
│  │   /api/papers/*         → papers_router                          │   │
│  │   /api/rag/*            → rag_router                             │   │
│  │   /api/ingest/*         → ingest_router                          │   │
│  │   /api/search/*         → search_router                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           SERVICES                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐    │
│  │ EmbeddingService│  │ VectorStoreService│  │ PDFProcessorService   │    │
│  │  (BGE-M3)      │  │  (LanceDB)     │  │  (GROBID+PyMuPDF)    │    │
│  └────────────────┘  └────────────────┘  └────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘

CICLO DE VIDA (LIFESPAN) EN FASTAPI
===================================

FastAPI 0.93+ usa el patrón "lifespan" en lugar de @app.on_event():

    Antiguo (deprecated):                  Nuevo (recomendado):
    ─────────────────────                  ────────────────────
    @app.on_event("startup")               @asynccontextmanager
    async def startup():                   async def lifespan(app):
        # init                                 # startup
                                               yield
    @app.on_event("shutdown")                  # shutdown
    async def shutdown():
        # cleanup

Ventajas del nuevo patrón:
- Context manager garantiza cleanup incluso con excepciones
- Estado compartido entre startup y shutdown
- Mejor soporte para testing
- Más Pythonic (usa "yield" como generadores)

CORS (Cross-Origin Resource Sharing)
====================================

CORS es un mecanismo de seguridad del navegador que bloquea peticiones
a dominios diferentes al de la página actual.

Sin CORS:
┌──────────────┐                    ┌──────────────┐
│  Frontend    │  → Request →      │   Backend    │
│  localhost:8501  │  ← BLOCKED ←  │  localhost:3690  │
└──────────────┘                    └──────────────┘
                    ❌ Browser bloquea

Con CORS Middleware:
┌──────────────┐                    ┌──────────────┐
│  Frontend    │  → Request →      │   Backend    │
│  localhost:8501  │  ← Response ←  │  localhost:3690  │
│              │    + CORS headers │              │
└──────────────┘                    └──────────────┘
                    ✓ Browser permite

Headers CORS importantes:
- Access-Control-Allow-Origin: * (quién puede hacer peticiones)
- Access-Control-Allow-Methods: * (qué métodos HTTP)
- Access-Control-Allow-Headers: * (qué headers custom)
- Access-Control-Allow-Credentials: true (cookies/auth)

NOTA DE SEGURIDAD:
- allow_origins=["*"] es permisivo (acepta cualquier origen)
- En producción, especificar: allow_origins=["http://localhost:8501"]
- Aquí usamos "*" porque es una app local/educativa

OPENAPI Y DOCUMENTACIÓN AUTOMÁTICA
==================================

FastAPI genera automáticamente:
- /docs      → Swagger UI (interfaz interactiva)
- /redoc     → ReDoc (documentación bonita)
- /openapi.json → Esquema OpenAPI 3.0

Los metadatos en FastAPI() aparecen en la documentación:
- title: Nombre de la API
- description: Descripción con Markdown
- version: Versión semántica

Stack: FastAPI + LanceDB + BGE-M3 + Ollama

Ejecución:
    # Desarrollo (con auto-reload):
    uvicorn app.main:app --reload --host 0.0.0.0 --port 3690

    # Producción (múltiples workers):
    uvicorn app.main:app --host 0.0.0.0 --port 3690 --workers 4

    # O usando la función main():
    python -m app.main
"""

# =============================================================================
# IMPORTS - Organizados por categoría
# =============================================================================

# ---------------------------------------------------------------------------
# Standard Library - Utilidades de contexto
# ---------------------------------------------------------------------------
import logging
import os
from contextlib import asynccontextmanager  # Para el patrón lifespan de FastAPI

# ---------------------------------------------------------------------------
# Third-party - Framework web
# ---------------------------------------------------------------------------
from fastapi import FastAPI  # El framework web principal
from fastapi.middleware.cors import CORSMiddleware  # Middleware para CORS headers

# ---------------------------------------------------------------------------
# Local - Configuración y servicios de la aplicación
# ---------------------------------------------------------------------------
from app.core.config import get_settings  # Singleton de configuración
from app.api import (
    papers_router,
    rag_router,
    ingest_router,
    search_router,
    instagram_router,
)
from app.services.vectorstore import get_vectorstore_service  # Singleton LanceDB
from app.services.embeddings import get_embedding_service  # Singleton BGE-M3
from app.services.content.scheduler import get_scheduler  # Instagram scheduler
from app.integrations.vital_sdk import VitalClient, VitalConfig  # vital-core SDK

log = logging.getLogger(__name__)


# =============================================================================
# LIFESPAN HANDLER - Ciclo de vida de la aplicación
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manejador del ciclo de vida de la aplicación FastAPI.

    Este async context manager se ejecuta:
    - ANTES del yield: Durante el startup (inicialización)
    - DESPUÉS del yield: Durante el shutdown (limpieza)

    PATRÓN DE EJECUCIÓN:
    ====================

        lifespan(app) se llama
               │
               ▼
        ┌──────────────────┐
        │  STARTUP PHASE   │  ← Código antes del yield
        │                  │
        │  - Crear dirs    │
        │  - Cargar modelos│
        │  - Conectar DB   │
        └────────┬─────────┘
                 │
                 ▼
            [yield]  ←── La app está corriendo, sirviendo requests
                 │
                 ▼
        ┌──────────────────┐
        │ SHUTDOWN PHASE   │  ← Código después del yield
        │                  │
        │  - Cerrar conex. │
        │  - Liberar mem.  │
        │  - Guardar cache │
        └──────────────────┘

    VENTAJAS DE PRE-INICIALIZAR SERVICIOS:
    ======================================

    1. Warm start: El primer request no sufre latencia de carga
    2. Fail fast: Errores de configuración detectados al arrancar
    3. Métricas limpias: El tiempo del primer request refleja
       solo el procesamiento, no la inicialización

    Args:
        app: La instancia de FastAPI (inyectada automáticamente)

    Yields:
        None: El control vuelve a FastAPI para servir requests

    Example:
        # Así se usa el lifespan en FastAPI:
        app = FastAPI(lifespan=lifespan)
    """
    # =========================================================================
    # FASE DE STARTUP - Se ejecuta al iniciar el servidor
    # =========================================================================

    # 1. Obtener configuración (singleton, se cachea)
    settings = get_settings()

    # 2. Crear directorios necesarios si no existen
    #    - data/papers/     → PDFs descargados
    #    - data/vectordb/   → Base de datos LanceDB
    #    - metadata/        → JSON con metadatos de papers
    #    - .cache/          → Cache de embeddings
    settings.ensure_directories()

    # 3. Pre-inicializar servicios pesados (lazy loading → eager loading)
    #    Esto carga los modelos en memoria ANTES del primer request
    #
    #    ¿Por qué es importante?
    #    - Cargar BGE-M3: ~2-3 segundos
    #    - Conectar LanceDB: ~100ms
    #
    #    Sin pre-init: El primer request tarda +3 segundos extra
    #    Con pre-init: Todos los requests son rápidos desde el inicio
    get_embedding_service()   # Carga BGE-M3 en GPU/CPU
    get_vectorstore_service() # Conecta a LanceDB

    # 4. Initialize vital-core SDK client (graceful -- does not block startup)
    vital_client: VitalClient | None = None
    vital_enabled = os.getenv("VITAL_ENABLED", "true").lower() in ("1", "true", "yes")
    if vital_enabled:
        try:
            vital_config = VitalConfig()  # type: ignore[call-arg]
            vital_client = VitalClient(config=vital_config)
            await vital_client.connect()
            await vital_client.register()
            log.info("Registered with vital-core as '%s'", vital_config.service_name)
        except Exception as exc:
            log.warning("vital-core integration unavailable: %s", exc)
            vital_client = None

    # Store on app.state so endpoints can publish events
    app.state.vital_client = vital_client

    # 5. Start Instagram content scheduler (no-op unless enabled in env)
    content_scheduler = get_scheduler()
    content_scheduler.start()
    app.state.content_scheduler = content_scheduler

    # =========================================================================
    # YIELD - La app está lista para servir requests
    # =========================================================================
    yield  # <- La app corre hasta que se apague

    # =========================================================================
    # FASE DE SHUTDOWN - Se ejecuta al apagar el servidor
    # =========================================================================
    content_scheduler.shutdown()

    if vital_client is not None:
        await vital_client.disconnect()
        log.info("Disconnected from vital-core")


# =============================================================================
# INSTANCIA DE LA APLICACIÓN FASTAPI
# =============================================================================
#
# FastAPI es el framework web moderno de Python. Características clave:
#
# COMPARACIÓN CON OTROS FRAMEWORKS:
# =================================
#
# │ Feature          │ FastAPI  │ Flask    │ Django   │
# ├──────────────────┼──────────┼──────────┼──────────┤
# │ Async nativo     │ ✓        │ ✗        │ ✓ (3.1+) │
# │ Type hints       │ ✓        │ ✗        │ ✗        │
# │ Validación auto  │ ✓        │ ✗        │ ✗        │
# │ OpenAPI auto     │ ✓        │ ✗        │ ✗        │
# │ Rendimiento      │ Alto     │ Medio    │ Medio    │
# │ Curva aprend.    │ Baja     │ Baja     │ Alta     │
#
# BENCHMARKS (requests/segundo):
# ==============================
# FastAPI + Uvicorn: ~30,000 req/s
# Flask + Gunicorn:  ~5,000 req/s
# Django + Gunicorn: ~3,000 req/s
#
# FastAPI usa Starlette (ASGI) internamente y Pydantic para validación.

app = FastAPI(
    # -------------------------------------------------------------------------
    # METADATOS OPENAPI - Aparecen en /docs y /redoc
    # -------------------------------------------------------------------------

    # Título de la API (aparece en la barra de título de Swagger)
    title="Scientific Library RAG",

    # Descripción en Markdown - Se renderiza en la documentación
    # Usamos triple quotes para formato legible
    description="""
    Biblioteca Científica Offline con Sistema RAG Local.

    Stack: FastAPI + LanceDB + BGE-M3 + Ollama

    ## Features

    - **Paper Discovery**: Search OpenAlex (240M+ papers), arXiv (2.5M+), PubMed
    - **PDF Processing**: GROBID for metadata, PyMuPDF4LLM for text extraction
    - **Vector Search**: LanceDB with BGE-M3 embeddings (1024 dims, 8K context)
    - **RAG Q&A**: Semantic search + LLM generation with Ollama
    - **Scientific Prizes**: Nobel API, Wikidata SPARQL for Fields Medal, Turing, etc.
    - **Caching**: Embedding cache, retrieval cache (30min TTL), semantic cache (0.95 threshold)

    ## Offline Capable

    Download papers when online, study completely offline with local LLM.
    """,

    # Versión semántica (MAJOR.MINOR.PATCH)
    # - MAJOR: Cambios que rompen compatibilidad
    # - MINOR: Nueva funcionalidad compatible
    # - PATCH: Fixes que no cambian la API
    version="1.0.0",

    # Callback de ciclo de vida (definido arriba)
    lifespan=lifespan,

    # Parámetros opcionales no usados aquí pero útiles:
    # docs_url="/docs",           # URL de Swagger UI (default: /docs)
    # redoc_url="/redoc",         # URL de ReDoc (default: /redoc)
    # openapi_url="/openapi.json" # URL del esquema (default: /openapi.json)
    # servers=[{"url": "http://localhost:3690"}]  # Para OpenAPI
)


# =============================================================================
# MIDDLEWARE CORS
# =============================================================================
#
# CORS = Cross-Origin Resource Sharing
#
# Problema que resuelve:
# ----------------------
# Los navegadores aplican "Same-Origin Policy" por seguridad.
# Sin CORS, el frontend (localhost:8501) no puede hacer fetch al
# backend (localhost:3690) porque son "orígenes diferentes".
#
# Origen = protocolo + dominio + puerto
#   - http://localhost:8501  ≠  http://localhost:3690  (diferente puerto)
#   - http://example.com     ≠  https://example.com    (diferente protocolo)
#
# FLUJO DE UNA PETICIÓN CORS:
# ===========================
#
#    Frontend (8501)                  Backend (3690)
#         │                                │
#         │──── OPTIONS /api/rag/query ───▶│  ← Preflight (automático)
#         │     Origin: localhost:8501     │
#         │                                │
#         │◀─── 200 OK ───────────────────│
#         │     Access-Control-Allow-Origin: *
#         │     Access-Control-Allow-Methods: *
#         │                                │
#         │──── POST /api/rag/query ──────▶│  ← Request real
#         │     Origin: localhost:8501     │
#         │                                │
#         │◀─── 200 OK + data ────────────│
#         │     Access-Control-Allow-Origin: *
#
#
# CONFIGURACIÓN DE CORS:
# ======================

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:8501,http://localhost:3690,http://localhost:8888"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REGISTRO DE ROUTERS
# =============================================================================
#
# Los routers organizan los endpoints en módulos separados.
# Cada router tiene un prefix y tags para la documentación.
#
# MAPA DE ENDPOINTS:
# ==================
#
# papers_router (/api/papers/):
#   ├── GET  /search/openalex  → Buscar en OpenAlex
#   ├── GET  /search/arxiv     → Buscar en arXiv
#   ├── GET  /by-doi/{doi}     → Paper por DOI
#   ├── GET  /by-arxiv/{id}    → Paper por ID arXiv
#   ├── GET  /oa-url/{doi}     → URL Open Access
#   └── POST /download/arxiv   → Descargar PDF arXiv
#
# rag_router (/api/rag/):
#   ├── POST /query            → Query RAG (síncrono)
#   ├── POST /query/stream     → Query RAG (streaming SSE)
#   ├── POST /search           → Solo búsqueda vectorial
#   └── POST /ask              → Query simple (alias)
#
# ingest_router (/api/ingest/):
#   ├── POST /pdf              → Ingestar PDF local
#   ├── POST /arxiv/{id}       → Descargar + ingestar arXiv
#   ├── POST /batch/arxiv      → Ingestar múltiples arXiv
#   ├── GET  /paper/{id}       → Estado de paper ingestado
#   └── POST /create-index     → Crear índice vectorial
#
# search_router (/api/search/):
#   ├── GET  /papers           → Buscar en vectorstore local
#   ├── GET  /nobel            → Buscar laureados Nobel
#   ├── GET  /fields-medal     → Medallas Fields
#   ├── GET  /turing-award     → Premio Turing
#   ├── GET  /abel-prize       → Premio Abel
#   └── GET  /prizes/{qid}     → Premios genéricos (Wikidata)

app.include_router(papers_router)    # Descubrimiento de papers externos
app.include_router(rag_router)       # Consultas RAG con LLM
app.include_router(ingest_router)    # Pipeline de ingestión de PDFs
app.include_router(search_router)    # Búsqueda local y premios científicos
app.include_router(instagram_router) # Automatización de contenido Instagram


# =============================================================================
# ENDPOINTS RAÍZ - Información y diagnóstico
# =============================================================================
#
# Estos endpoints están en la raíz (sin prefix) porque son utilitarios
# generales, no específicos de ningún dominio de la API.


@app.get("/")
async def root():
    """
    Endpoint raíz - Información básica de la API.

    Este endpoint sirve como "tarjeta de presentación" de la API.
    Es útil para:
    - Verificar que el servidor está corriendo
    - Descubrir la documentación
    - Obtener la versión actual

    CONVENCIÓN REST:
    ================
    El endpoint raíz "/" típicamente retorna metadatos de la API.
    Es el equivalente a un "Hello World" pero útil.

    RESPUESTA:
    ==========
    {
        "name": "Scientific Library RAG",  # Nombre de la API
        "version": "1.0.0",                # Versión actual
        "docs": "/docs",                   # Link a Swagger UI
        "redoc": "/redoc"                  # Link a ReDoc
    }

    Returns:
        dict: Metadatos de la API con links a documentación

    Example:
        curl http://localhost:3690/
    """
    return {
        "name": "Scientific Library RAG",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
async def health():
    """
    Health check endpoint - Diagnóstico del estado del sistema.

    Los health checks son esenciales para:
    1. Load balancers (saber si el servidor puede recibir tráfico)
    2. Kubernetes (liveness/readiness probes)
    3. Monitoreo (alertas cuando algo falla)
    4. Debugging (verificar estado de servicios)

    TIPOS DE HEALTH CHECKS:
    =======================

    │ Tipo        │ Propósito                    │ Acción si falla        │
    ├─────────────┼──────────────────────────────┼────────────────────────┤
    │ Liveness    │ ¿El proceso está vivo?       │ Reiniciar contenedor   │
    │ Readiness   │ ¿Puede recibir tráfico?      │ Quitar del balanceador │
    │ Startup     │ ¿Terminó de inicializar?     │ Esperar más tiempo     │

    Este endpoint combina liveness + readiness:
    - Verifica que los servicios críticos funcionan
    - Retorna estadísticas de cache y vectorstore

    ESTRUCTURA DE RESPUESTA:
    ========================
    {
        "status": "healthy",           # Estado general
        "embedding_model": "BAAI/...", # Modelo de embeddings cargado
        "embedding_cache": {           # Estadísticas del cache
            "hits": 1500,
            "misses": 50,
            "size": 1550
        },
        "vectorstore": {               # Estado de LanceDB
            "num_documents": 5000,
            "num_chunks": 25000
        }
    }

    Returns:
        dict: Estado de salud con métricas de servicios

    Example:
        curl http://localhost:3690/health

        # En Kubernetes:
        livenessProbe:
          httpGet:
            path: /health
            port: 3690
          initialDelaySeconds: 30
          periodSeconds: 10
    """
    # Obtener settings (no se usa directamente, pero podría añadirse info)
    settings = get_settings()

    # Obtener instancias de servicios (singletons, ya inicializados)
    embedding_service = get_embedding_service()
    vectorstore = get_vectorstore_service()

    # Retornar estado completo
    # Si algún servicio fallara, este endpoint lanzaría excepción
    # y retornaría 500, indicando que el sistema no está healthy
    return {
        "status": "healthy",
        "embedding_model": embedding_service.model,  # Ej: "BAAI/bge-m3"
        "embedding_cache": embedding_service.get_cache_stats(),  # hits, misses, size
        "vectorstore": vectorstore.get_stats(),  # num_documents, num_chunks
    }


@app.get("/stats")
async def stats():
    """
    System statistics endpoint - Métricas detalladas del sistema.

    Similar a /health pero enfocado en estadísticas operacionales
    en lugar de diagnóstico de estado.

    DIFERENCIA ENTRE /health Y /stats:
    ==================================

    /health:
    - Propósito: ¿El sistema funciona?
    - Respuesta: Simple, rápida
    - Usuario: Load balancers, Kubernetes
    - Frecuencia: Cada segundos

    /stats:
    - Propósito: ¿Cómo está funcionando?
    - Respuesta: Detallada, métricas
    - Usuario: Dashboards, debugging
    - Frecuencia: Cada minutos

    MÉTRICAS INCLUIDAS:
    ===================

    vectorstore:
      - num_documents: Total de papers indexados
      - num_chunks: Total de chunks vectorizados
      - index_size: Tamaño del índice en bytes

    embeddings:
      - cache_hits: Embeddings servidos desde cache
      - cache_misses: Embeddings calculados
      - hit_rate: cache_hits / (hits + misses)

    USO PARA DASHBOARDS:
    ====================

    Ejemplo con Prometheus + Grafana:
    1. Prometheus scrape este endpoint
    2. Grafana grafica las métricas
    3. Alertas cuando hit_rate < 0.80

    Returns:
        dict: Estadísticas detalladas del vectorstore y embeddings

    Example:
        curl http://localhost:3690/stats | jq
    """
    # Obtener servicios
    vectorstore = get_vectorstore_service()
    embedding_service = get_embedding_service()

    return {
        "vectorstore": vectorstore.get_stats(),
        "embeddings": embedding_service.get_cache_stats(),
    }


# =============================================================================
# FUNCIÓN MAIN - Punto de entrada para ejecución directa
# =============================================================================

def main():
    """
    Ejecutar la aplicación con Uvicorn.

    Esta función permite ejecutar la app directamente con:
        python -m app.main

    UVICORN - SERVIDOR ASGI:
    ========================

    Uvicorn es el servidor ASGI recomendado para FastAPI.

    ASGI vs WSGI:
    ─────────────
    │ WSGI (Flask, Django)    │ ASGI (FastAPI, Starlette)  │
    ├─────────────────────────┼────────────────────────────┤
    │ Síncrono                │ Asíncrono                  │
    │ 1 request = 1 thread    │ 1 request = 1 coroutine    │
    │ Gunicorn                │ Uvicorn                    │
    │ ~5K req/s               │ ~30K req/s                 │

    PARÁMETROS DE UVICORN:
    ======================

    Desarrollo:
    -----------
    uvicorn.run(
        "app.main:app",  # Módulo:variable (string para reload)
        host="0.0.0.0",  # Escuchar en todas las interfaces
        port=3690,       # Puerto
        reload=True,     # Auto-reload al cambiar código
        workers=1        # Un solo worker (reload no soporta múltiples)
    )

    Producción:
    -----------
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=3690,
        reload=False,    # Sin reload (overhead innecesario)
        workers=4        # Múltiples workers (1 por CPU core)
    )

    ¿POR QUÉ "app.main:app" COMO STRING?
    =====================================

    Si pasamos la instancia directamente (app), el reload no funciona
    porque no puede reimportar el módulo.

    Con string, Uvicorn sabe cómo importar el módulo fresco en cada reload.

    ALTERNATIVA CON GUNICORN (producción):
    ======================================

    Para producción real, Gunicorn + Uvicorn workers:

        gunicorn app.main:app \\
            --workers 4 \\
            --worker-class uvicorn.workers.UvicornWorker \\
            --bind 0.0.0.0:3690

    Gunicorn maneja los workers, Uvicorn maneja ASGI.
    """
    # Importar uvicorn aquí para evitar importación innecesaria
    # si solo se usa la app como módulo (ej: en tests)
    import uvicorn

    # Obtener configuración
    settings = get_settings()

    # Iniciar servidor
    uvicorn.run(
        "app.main:app",       # Ruta al objeto app (string para reload)
        host=settings.host,   # "0.0.0.0" para escuchar en todas las interfaces
        port=settings.port,   # 3690 (configurado en settings)
        reload=settings.debug, # True en desarrollo, False en producción
        workers=settings.workers,  # Número de workers (1 en debug, N en prod)
    )


# =============================================================================
# EJECUCIÓN DIRECTA
# =============================================================================
#
# Este bloque permite ejecutar el módulo directamente:
#   python -m app.main
#   python app/main.py
#
# __name__ == "__main__" es True solo cuando el archivo se ejecuta
# directamente, no cuando se importa como módulo.

if __name__ == "__main__":
    main()
