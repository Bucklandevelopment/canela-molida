"""
================================================================================
MODELOS RAG (RETRIEVAL-AUGMENTED GENERATION) - BIBLIOTECA CIENTÍFICA
================================================================================

Este módulo define los modelos de datos para el pipeline RAG, que combina
recuperación de información con generación de lenguaje natural.

¿QUÉ ES RAG?
============

RAG (Retrieval-Augmented Generation) es un patrón arquitectónico que mejora
las respuestas de LLMs con información contextual relevante:

    ┌────────────────────────────────────────────────────────────────────────┐
    │                        PIPELINE RAG                                    │
    │                                                                        │
    │   ┌─────────┐    ┌────────────┐    ┌────────────┐    ┌─────────────┐  │
    │   │ Usuario │───▶│ Embedding  │───▶│ Vector DB  │───▶│   Contexto  │  │
    │   │ Query   │    │  BGE-M3    │    │  LanceDB   │    │  Relevante  │  │
    │   └─────────┘    └────────────┘    └────────────┘    └──────┬──────┘  │
    │                                                             │         │
    │                                                             ▼         │
    │   ┌─────────┐    ┌────────────┐    ┌────────────────────────────────┐ │
    │   │Respuesta│◀───│   LLM      │◀───│ Prompt = Query + Contexto      │ │
    │   │  Final  │    │ Llama 3.1  │    │              Científico        │ │
    │   └─────────┘    └────────────┘    └────────────────────────────────┘ │
    └────────────────────────────────────────────────────────────────────────┘

¿POR QUÉ RAG EN VEZ DE FINE-TUNING?
===================================

    ┌────────────────────────────────────────────────────────────────────┐
    │ Aspecto         │ RAG                    │ Fine-tuning             │
    ├─────────────────┼────────────────────────┼─────────────────────────┤
    │ Actualización   │ Inmediata              │ Requiere re-entrenar    │
    │ Costo           │ Solo inferencia        │ GPU × horas             │
    │ Alucinaciones   │ Reducidas (grounded)   │ Persisten               │
    │ Trazabilidad    │ Citas directas         │ Caja negra              │
    │ Escalabilidad   │ Millones de docs       │ Limitado por contexto   │
    └────────────────────────────────────────────────────────────────────┘

    Para una biblioteca científica, RAG es ideal porque:
    - Los papers se publican constantemente (actualización continua)
    - Las citas son obligatorias (trazabilidad)
    - El conocimiento está en los documentos, no necesita memorizarse

SISTEMA DE CACHÉ SEMÁNTICO
==========================

El caché semántico es la innovación clave para rendimiento:

    ┌──────────────────────────────────────────────────────────────────────┐
    │                    FLUJO DE CACHÉ SEMÁNTICO                          │
    │                                                                      │
    │   Query entrante: "¿Qué es un transformer?"                         │
    │                          │                                           │
    │                          ▼                                           │
    │              ┌──────────────────────┐                                │
    │              │  Vectorizar query    │                                │
    │              │  con BGE-M3          │                                │
    │              └──────────────────────┘                                │
    │                          │                                           │
    │                          ▼                                           │
    │              ┌──────────────────────┐                                │
    │              │  Buscar en caché     │                                │
    │              │  similarity > 0.95   │                                │
    │              └──────────────────────┘                                │
    │                    │           │                                     │
    │               HIT  │           │ MISS                                │
    │                    ▼           ▼                                     │
    │   ┌─────────────────────┐  ┌─────────────────────┐                   │
    │   │ Retornar respuesta  │  │ Ejecutar RAG full   │                   │
    │   │ cacheada (~50ms)    │  │ + guardar en caché  │                   │
    │   └─────────────────────┘  └─────────────────────┘                   │
    └──────────────────────────────────────────────────────────────────────┘

    UMBRAL DE SIMILITUD 0.95
    ------------------------
    - Muy alto: Solo queries casi idénticas
    - "¿Qué es un transformer?" ≈ "¿Qué son los transformers?" (0.96)
    - "¿Qué es un transformer?" ≠ "¿Cómo funcionan los CNNs?" (0.45)

    SPEEDUP: ~65x para queries cacheadas
    - Sin caché: 3000-5000ms (retrieval + LLM)
    - Con caché: 50-80ms (solo vector search + lookup)

Supports semantic caching with 0.95 similarity threshold.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# MODELO: RETRIEVED CONTEXT (CONTEXTO RECUPERADO)
# =============================================================================

class RetrievedContext(BaseModel):
    """
    Contexto recuperado del vector store para alimentar al LLM.

    ESTRUCTURA DE CONTEXTO
    ======================

    Cada contexto representa un chunk relevante encontrado:

        ┌─────────────────────────────────────────────────────────────┐
        │                  RetrievedContext                           │
        ├─────────────────────────────────────────────────────────────┤
        │  paper_id: "10.1038/nature12373"                           │
        │  chunk_index: 5                                             │
        │  text: "The transformer architecture..."                    │
        │  score: 0.89 (similitud coseno)                            │
        │                                                             │
        │  # Para citas en la respuesta:                             │
        │  title: "Attention Is All You Need"                         │
        │  authors: ["Vaswani", "Shazeer", ...]                      │
        │  year: 2017                                                 │
        │  doi: "10.48550/arXiv.1706.03762"                          │
        └─────────────────────────────────────────────────────────────┘

    ¿POR QUÉ DENORMALIZAR?
    ======================

    Incluimos title, authors, year, doi directamente en el contexto
    (en lugar de solo paper_id) porque:

    1. RENDIMIENTO: Evita JOINs en tiempo de respuesta
       - El RAG ya encontró estos datos durante la búsqueda
       - Guardarlos evita otra consulta a la DB

    2. CITAS: El LLM necesita estos datos para citar
       - El prompt incluye "Cita las fuentes con [Autor, Año]"
       - Sin estos datos, las citas serían imposibles

    3. STREAMING: El contexto se serializa una vez
       - Durante streaming, no podemos hacer queries adicionales
       - Todo debe estar disponible al inicio

    ORDENAMIENTO POR SCORE
    ======================

    Los contextos se ordenan por relevancia (score descendente):

        1. score=0.95 → Chunk más relevante (primero en el prompt)
        2. score=0.89 → Segundo más relevante
        3. score=0.82 → Tercero más relevante
        ...

    Esto importa porque los LLMs dan más peso al texto inicial.

    Attributes:
        paper_id: ID del paper origen
        chunk_index: Índice del chunk en el paper
        text: Contenido textual del chunk
        score: Similitud coseno [0, 1]
        title: Título del paper (para citas)
        authors: Lista de nombres de autores
        year: Año de publicación
        doi: DOI si disponible
        arxiv_id: arXiv ID si disponible
    """

    # -------------------------------------------------------------------------
    # IDENTIFICACIÓN DEL CHUNK
    # -------------------------------------------------------------------------

    # ID del paper que contiene este chunk
    # Usado para agrupar contextos del mismo paper
    paper_id: str

    # Índice del chunk dentro del paper
    # Permite reconstruir orden original si es necesario
    chunk_index: int

    # -------------------------------------------------------------------------
    # CONTENIDO
    # -------------------------------------------------------------------------

    # Texto del chunk recuperado
    # Este es el contenido que se inyecta en el prompt del LLM
    text: str

    # Score de similitud coseno con la query
    # Rango: [0, 1] donde 1 = idéntico semánticamente
    # Típicamente >0.7 para resultados útiles
    score: float

    # -------------------------------------------------------------------------
    # METADATOS PARA CITAS (DENORMALIZADOS)
    # -------------------------------------------------------------------------

    # Título del paper - esencial para citas legibles
    # Ej: "Attention Is All You Need"
    title: str

    # Lista de nombres de autores
    # Para citas tipo [Vaswani et al., 2017]
    # Típicamente primer autor + "et al." si >2
    authors: list[str] = Field(default_factory=list)

    # Año de publicación
    # Para citas tipo [Autor, Año]
    year: Optional[int] = None

    # DOI para enlace directo
    # Permite "Ver paper original" en UI
    doi: Optional[str] = None

    # arXiv ID como alternativa al DOI
    # Para preprints sin DOI formal
    arxiv_id: Optional[str] = None


# =============================================================================
# MODELO: RAG QUERY (CONSULTA AL SISTEMA RAG)
# =============================================================================

class RAGQuery(BaseModel):
    """
    Consulta para el sistema de Question-Answering basado en RAG.

    ANATOMÍA DE UNA CONSULTA RAG
    ============================

    Una query RAG tiene varios componentes configurables:

        ┌────────────────────────────────────────────────────────────────┐
        │                      RAGQuery                                  │
        │                                                                │
        │  question: "¿Qué mejoras introduce GPT-4 sobre GPT-3?"        │
        │                                                                │
        │  ┌─ Retrieval ─────────────────────────────────────────────┐  │
        │  │  top_k: 10        ← Chunks a recuperar                  │  │
        │  │  year_min: 2020   ← Filtro temporal                     │  │
        │  │  categories: []   ← Filtro por área                     │  │
        │  └─────────────────────────────────────────────────────────┘  │
        │                                                                │
        │  ┌─ Generation ────────────────────────────────────────────┐  │
        │  │  max_context_tokens: 4096  ← Contexto máximo            │  │
        │  │  temperature: 0.7          ← Creatividad del LLM        │  │
        │  │  include_sources: true     ← Incluir citas              │  │
        │  └─────────────────────────────────────────────────────────┘  │
        │                                                                │
        │  ┌─ Optimización ──────────────────────────────────────────┐  │
        │  │  use_semantic_cache: true  ← Usar caché semántico       │  │
        │  └─────────────────────────────────────────────────────────┘  │
        └────────────────────────────────────────────────────────────────┘

    PARÁMETROS DE RETRIEVAL
    =======================

    top_k: Número de chunks a recuperar
    -----------------------------------
        - Muy bajo (3-5): Riesgo de perder información relevante
        - Muy alto (50+): Dilución, más tokens, más costo
        - Óptimo (10-15): Balance para papers científicos

    Filtros (year_min, year_max, categories)
    ----------------------------------------
        - Mejoran precisión al limitar el espacio de búsqueda
        - Ejemplo: "papers de NLP desde 2020" → categories=["cs.CL"], year_min=2020

    PARÁMETROS DE GENERACIÓN
    ========================

    max_context_tokens: Límite de contexto
    --------------------------------------
        - Llama 3.1 8B: 8192 tokens de contexto
        - Reservar ~2000 para respuesta
        - Default 4096 es conservador

    temperature: Control de creatividad
    -----------------------------------
        - 0.0: Determinístico, repite texto
        - 0.7: Balance (recomendado para Q&A)
        - 1.0+: Más creativo, menos factual

    CACHÉ SEMÁNTICO
    ===============

    use_semantic_cache controla si buscar en caché primero:
        - true (default): Buscar query similar antes de RAG completo
        - false: Siempre ejecutar pipeline completo (debugging)

    Attributes:
        question: Pregunta del usuario
        top_k: Número de chunks a recuperar (1-50)
        year_min: Filtro año mínimo
        year_max: Filtro año máximo
        categories: Filtro por categorías arXiv
        include_sources: Si incluir fuentes en respuesta
        max_context_tokens: Límite de tokens de contexto
        temperature: Creatividad del LLM (0-2)
        use_semantic_cache: Si usar caché semántico
    """

    # -------------------------------------------------------------------------
    # PREGUNTA PRINCIPAL
    # -------------------------------------------------------------------------

    # Pregunta del usuario en lenguaje natural
    # Se vectoriza para búsqueda y se incluye en el prompt
    question: str

    # -------------------------------------------------------------------------
    # PARÁMETROS DE RETRIEVAL
    # -------------------------------------------------------------------------

    # Número de chunks más relevantes a recuperar
    # Rango: 1-50 (limitado para rendimiento y contexto)
    # Default: 10 (óptimo para papers científicos)
    top_k: int = Field(default=10, ge=1, le=50)

    # Filtros temporales - se propagan al vector store
    year_min: Optional[int] = None
    year_max: Optional[int] = None

    # Filtro por categorías arXiv
    # Operador: OR (cualquier categoría)
    # Vacío = todas las categorías
    categories: list[str] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # PARÁMETROS DE GENERACIÓN
    # -------------------------------------------------------------------------

    # Si incluir fuentes/citas en la respuesta
    # True: LLM citará papers con [Autor, Año]
    # False: Respuesta sin citas (más corta)
    include_sources: bool = True

    # Máximo de tokens de contexto para el LLM
    # Contexto = chunks concatenados + metadatos
    # Más contexto = más información pero más lento
    max_context_tokens: int = 4096

    # Temperature para generación del LLM
    # 0.0 = Determinístico (mismo output siempre)
    # 0.7 = Balance creatividad/factualidad (default)
    # 2.0 = Máxima creatividad (no recomendado para Q&A)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # -------------------------------------------------------------------------
    # OPTIMIZACIÓN
    # -------------------------------------------------------------------------

    # Control del caché semántico
    # True: Buscar query similar antes de RAG completo
    # False: Bypass del caché (útil para debugging/testing)
    use_semantic_cache: bool = True


# =============================================================================
# MODELO: RAG RESPONSE (RESPUESTA DEL SISTEMA RAG)
# =============================================================================

class RAGResponse(BaseModel):
    """
    Respuesta completa del pipeline RAG.

    ESTRUCTURA DE RESPUESTA
    =======================

    Una respuesta RAG contiene múltiples capas de información:

        ┌────────────────────────────────────────────────────────────────┐
        │                      RAGResponse                               │
        │                                                                │
        │  question: "¿Qué es el mecanismo de atención?"                │
        │                                                                │
        │  answer: "El mecanismo de atención es una técnica que         │
        │           permite a los modelos enfocarse en partes           │
        │           relevantes del input [Vaswani et al., 2017]..."     │
        │                                                                │
        │  contexts: [                                                   │
        │    {paper_id: "...", text: "...", score: 0.95},              │
        │    {paper_id: "...", text: "...", score: 0.89},              │
        │    ...                                                         │
        │  ]                                                             │
        │                                                                │
        │  metadata: {                                                   │
        │    model: "llama3.1:8b",                                      │
        │    retrieved_count: 10,                                        │
        │    used_cache: false,                                          │
        │    retrieval_time_ms: 150,                                     │
        │    generation_time_ms: 2800,                                   │
        │    total_time_ms: 2950                                         │
        │  }                                                             │
        └────────────────────────────────────────────────────────────────┘

    TIMING BREAKDOWN
    ================

    El desglose de tiempos ayuda a identificar cuellos de botella:

        retrieval_time_ms   │ Vector search + filtros
        generation_time_ms  │ LLM inference
        ────────────────────┼────────────────────────────
        TOTAL              │ retrieval + generation

    Típicamente:
        - Retrieval: 50-200ms (LanceDB es muy rápido)
        - Generation: 2000-5000ms (depende del modelo y GPU/CPU)

    Si retrieval >> generation: Problema de índices
    Si generation >> retrieval: Normal (LLM es el cuello de botella)

    RESPUESTA CACHEADA
    ==================

    Cuando used_cache=True:
        - answer viene del caché, no del LLM
        - generation_time_ms ≈ 0
        - total_time_ms ≈ retrieval_time_ms (solo búsqueda en caché)
        - query_embedding se usó para encontrar el match

    STREAMING
    =========

    Para streaming (Server-Sent Events):
        - La respuesta se serializa parcialmente
        - answer se envía token por token
        - contexts se envían al inicio
        - metadata se envía al final

    Attributes:
        question: Echo de la pregunta original
        answer: Respuesta generada por el LLM
        contexts: Lista de contextos usados
        model: Modelo LLM usado
        retrieved_count: Chunks recuperados
        used_cache: Si vino del caché
        retrieval_time_ms: Tiempo de retrieval
        generation_time_ms: Tiempo de generación
        total_time_ms: Tiempo total
        query_embedding: Vector de la query (para caché)
        created_at: Timestamp de creación
    """

    # -------------------------------------------------------------------------
    # ECHO DE LA QUERY
    # -------------------------------------------------------------------------

    # Pregunta original (echo para logging/debugging)
    question: str

    # -------------------------------------------------------------------------
    # RESPUESTA GENERADA
    # -------------------------------------------------------------------------

    # Respuesta del LLM en lenguaje natural
    # Incluye citas si include_sources=True en la query
    # Formato markdown (headers, listas, **bold**, etc.)
    answer: str

    # -------------------------------------------------------------------------
    # FUENTES/CONTEXTOS
    # -------------------------------------------------------------------------

    # Lista de contextos recuperados y usados
    # Ordenados por relevancia (score descendente)
    # Útiles para verificación y "ver más"
    contexts: list[RetrievedContext] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # METADATOS DEL MODELO
    # -------------------------------------------------------------------------

    # Identificador del modelo LLM usado
    # Ej: "llama3.1:8b", "qwen2:7b"
    # Importante para reproducibilidad
    model: str

    # Número de chunks recuperados del vector store
    # Puede ser menor que top_k si no hay suficientes results
    retrieved_count: int

    # Flag indicando si la respuesta vino del caché semántico
    # True: Respuesta cacheada (muy rápida)
    # False: Respuesta generada en tiempo real
    used_cache: bool = False

    # -------------------------------------------------------------------------
    # MÉTRICAS DE TIEMPO
    # -------------------------------------------------------------------------

    # Tiempo de retrieval en milisegundos
    # Incluye: embedding query + vector search + post-filtrado
    retrieval_time_ms: float

    # Tiempo de generación en milisegundos
    # Incluye: prompt construction + LLM inference
    # 0 si used_cache=True
    generation_time_ms: float

    # Tiempo total del pipeline
    # total = retrieval + generation + overhead
    total_time_ms: float

    # -------------------------------------------------------------------------
    # DATOS PARA CACHING
    # -------------------------------------------------------------------------

    # Embedding de la query para caché semántico
    # Se guarda junto con la respuesta para lookup futuro
    # 1024 dimensiones (BGE-M3)
    query_embedding: Optional[list[float]] = None

    # Timestamp de creación de la respuesta
    # Para TTL del caché y ordenamiento
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# MODELO: SEMANTIC CACHE ENTRY (ENTRADA DE CACHÉ SEMÁNTICO)
# =============================================================================

class SemanticCacheEntry(BaseModel):
    """
    Entrada en el caché semántico para pares query-response.

    ARQUITECTURA DEL CACHÉ SEMÁNTICO
    ================================

    El caché semántico es fundamentalmente diferente del caché tradicional:

        ┌─────────────────────────────────────────────────────────────────┐
        │              CACHÉ TRADICIONAL (key-value)                      │
        │                                                                 │
        │   Key exacto         │ Valor                                   │
        │   ─────────────────────────────────────────────────────────    │
        │   "qué es atención"  │ "La atención es..."                     │
        │   "que es atencion"  │ MISS (key diferente)                    │
        │                                                                 │
        │   Problema: Variaciones mínimas = cache miss                   │
        └─────────────────────────────────────────────────────────────────┘

        ┌─────────────────────────────────────────────────────────────────┐
        │              CACHÉ SEMÁNTICO (vector similarity)                │
        │                                                                 │
        │   Query           │ Embedding      │ Similitud   │ Resultado   │
        │   ────────────────────────────────────────────────────────────  │
        │   "qué es         │ [0.23, 0.45..] │ 1.00        │ HIT         │
        │    atención"      │                │             │             │
        │   "que es         │ [0.23, 0.44..] │ 0.98        │ HIT (>0.95) │
        │    atencion"      │                │             │             │
        │   "explain        │ [0.22, 0.46..] │ 0.96        │ HIT (>0.95) │
        │    attention"     │                │             │             │
        │                                                                 │
        │   Ventaja: Queries semánticamente equivalentes = hit           │
        └─────────────────────────────────────────────────────────────────┘

    ALMACENAMIENTO EN LANCEDB
    =========================

    El caché se almacena en una tabla "semantic_cache" con esquema:

        query: string            ← Query original (para debugging)
        query_embedding: float[1024]  ← Vector para búsqueda
        response: JSON           ← RAGResponse serializada
        created_at: timestamp    ← Para TTL
        hit_count: int32         ← Estadísticas de uso

    BÚSQUEDA EN CACHÉ
    =================

        1. Vectorizar nueva query con BGE-M3
        2. Buscar en semantic_cache con similarity > 0.95
        3. Si HIT: Retornar response deserializada
        4. Si MISS: Ejecutar RAG completo y cachear

    UMBRAL 0.95
    ===========

    El umbral de 0.95 es crítico:

        - Demasiado bajo (0.85): Falsas coincidencias
          "¿Qué es attention?" ↔ "¿Qué es convolution?" (0.88)

        - Demasiado alto (0.99): Pocas coincidencias
          Solo queries casi idénticas

        - 0.95 es el sweet spot para preguntas en lenguaje natural
          Tolerante a reformulaciones pero no a cambios de tema

    GESTIÓN DEL CACHÉ
    =================

        - Tamaño: Sin límite explícito (LanceDB escala bien)
        - TTL: Implícito por created_at (queries pueden invalidarse)
        - Invalidación: Por cambios en el corpus (reindexación)
        - hit_count: Para analytics y posible eviction LRU

    Stored in vector store, returns cached response if similarity > 0.95.
    Reduces latency up to 65x for repeated/similar queries.

    Attributes:
        query: Query original almacenada
        query_embedding: Vector BGE-M3 de la query (1024 dims)
        response: RAGResponse completa serializada
        created_at: Timestamp de creación
        hit_count: Número de veces que se ha usado este cache entry
    """

    # -------------------------------------------------------------------------
    # QUERY ALMACENADA
    # -------------------------------------------------------------------------

    # Query original en texto
    # Guardada para debugging y logging
    # No se usa para búsqueda (se usa el embedding)
    query: str

    # Embedding de la query con BGE-M3
    # Vector de 1024 dimensiones
    # Este es el campo indexado para búsqueda por similitud
    query_embedding: list[float]

    # -------------------------------------------------------------------------
    # RESPUESTA CACHEADA
    # -------------------------------------------------------------------------

    # RAGResponse completa serializada
    # Incluye: answer, contexts, timing, etc.
    # Se deserializa al hacer hit en el caché
    response: RAGResponse

    # -------------------------------------------------------------------------
    # METADATOS
    # -------------------------------------------------------------------------

    # Timestamp de cuando se creó esta entrada
    # Útil para:
    #   - TTL (time-to-live) del caché
    #   - Invalidación por antigüedad
    #   - Ordenamiento cronológico
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Contador de hits para esta entrada
    # Se incrementa cada vez que se retorna esta respuesta
    # Útil para:
    #   - Analytics de queries populares
    #   - Decisiones de eviction (mantener entries populares)
    #   - Monitoreo de eficacia del caché
    hit_count: int = 0
