"""
================================================================================
SERVICIO RAG (RETRIEVAL-AUGMENTED GENERATION) - BIBLIOTECA CIENTÍFICA
================================================================================

Este módulo implementa el pipeline RAG completo, combinando recuperación de
información vectorial con generación de respuestas mediante LLM.

¿QUÉ ES RAG?
============

RAG es un paradigma que mejora las capacidades de los LLMs con conocimiento externo:

    ┌────────────────────────────────────────────────────────────────────────────┐
    │                          ARQUITECTURA RAG                                  │
    │                                                                            │
    │   Usuario: "¿Qué es el mecanismo de atención en transformers?"            │
    │                                                                            │
    │   ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────┐   │
    │   │   QUERY     │ ───▶ │  EMBEDDING  │ ───▶ │   VECTOR SEARCH         │   │
    │   │             │      │   BGE-M3    │      │   LanceDB               │   │
    │   │ "¿Qué es    │      │             │      │                         │   │
    │   │  atención?" │      │ → [0.2,     │      │ → Top-K chunks          │   │
    │   │             │      │    0.5,...] │      │   relevantes            │   │
    │   └─────────────┘      └─────────────┘      └───────────┬─────────────┘   │
    │                                                         │                  │
    │                                                         ▼                  │
    │   ┌─────────────────────────────────────────────────────────────────────┐ │
    │   │                        PROMPT AUGMENTADO                            │ │
    │   │                                                                     │ │
    │   │ System: "Eres un asistente científico..."                          │ │
    │   │                                                                     │ │
    │   │ Context:                                                            │ │
    │   │   [Attention Is All You Need - Vaswani et al.]                     │ │
    │   │   "The transformer architecture uses self-attention..."            │ │
    │   │   ---                                                               │ │
    │   │   [BERT - Devlin et al.]                                           │ │
    │   │   "Bidirectional attention allows..."                              │ │
    │   │                                                                     │ │
    │   │ Question: "¿Qué es el mecanismo de atención?"                      │ │
    │   └───────────────────────────────────────────────────────┬─────────────┘ │
    │                                                           │               │
    │                                                           ▼               │
    │   ┌─────────────────────────────────────────────────────────────────────┐ │
    │   │                           LLM                                       │ │
    │   │                    (Llama 3.1 8B / Qwen2 7B)                        │ │
    │   └───────────────────────────────────────────────────────┬─────────────┘ │
    │                                                           │               │
    │                                                           ▼               │
    │   Respuesta: "El mecanismo de atención es una técnica que permite       │
    │              a los modelos asignar diferentes pesos a partes del        │
    │              input. Según Vaswani et al. (2017), el self-attention..."  │
    └────────────────────────────────────────────────────────────────────────────┘

¿POR QUÉ RAG PARA PAPERS CIENTÍFICOS?
=====================================

RAG es ideal para bibliotecas científicas por:

    ┌────────────────────────────────────────────────────────────────────┐
    │ Ventaja           │ Explicación                                   │
    ├───────────────────┼───────────────────────────────────────────────┤
    │ Actualización     │ Nuevos papers = indexar y listo               │
    │ Sin fine-tuning   │ No requiere GPU para entrenar                 │
    │ Citaciones        │ Puede citar fuentes específicas               │
    │ Verificabilidad   │ El contexto permite verificar respuestas      │
    │ Escalabilidad     │ Millones de papers sin re-entrenar            │
    │ Multilingüe       │ BGE-M3 soporta 100+ idiomas                   │
    └────────────────────────────────────────────────────────────────────┘

PIPELINE DETALLADO
==================

El pipeline tiene 6 pasos:

    1. CHECK SEMANTIC CACHE
       ─────────────────────
       ¿Hay query similar (>0.95) en caché?
       SÍ → Retornar respuesta cacheada (~50ms)
       NO → Continuar

    2. QUERY EMBEDDING
       ─────────────────
       Convertir query a vector 1024D con BGE-M3

    3. VECTOR SEARCH
       ─────────────────
       Buscar top-K chunks más similares en LanceDB
       Aplicar filtros (año, categorías)

    4. CONTEXT ASSEMBLY
       ─────────────────
       Construir contexto con citas:
       "[Título - Autor et al.]\nTexto del chunk..."

    5. LLM GENERATION
       ─────────────────
       Enviar prompt a Llama 3.1 / Qwen2
       System prompt científico + contexto + pregunta

    6. RESPONSE CACHING
       ─────────────────
       Guardar en semantic cache para queries futuros

LATENCIA TÍPICA
===============

    ┌────────────────────────────────────────────────────────────────────┐
    │ Etapa              │ Tiempo típico    │ Con caché                │
    ├────────────────────┼──────────────────┼──────────────────────────┤
    │ Semantic cache     │ 10-30ms          │ → Si HIT, total ~50ms    │
    │ Query embedding    │ 50-100ms         │ (cacheado en disco)      │
    │ Vector search      │ 20-100ms         │ (retrieval cache 30min)  │
    │ Context assembly   │ ~5ms             │                          │
    │ LLM generation     │ 2000-5000ms      │ ← Cuello de botella      │
    │ ─────────────────  │ ─────────────    │                          │
    │ TOTAL              │ 2000-5300ms      │ ~50ms con semantic cache │
    └────────────────────────────────────────────────────────────────────┘

    Speedup con semantic cache: ~65x para queries repetidos/similares

Pipeline:
1. Query embedding with BGE-M3
2. Vector search in LanceDB
3. Semantic cache check (threshold 0.95 for 65x speedup)
4. Context assembly
5. LLM generation with Ollama (Llama 3.1 8B)
6. Response caching

Uses LangChain for pipeline orchestration.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import time                      # Para medir latencias del pipeline
from functools import lru_cache  # Singleton pattern
from typing import Optional

import ollama                    # Cliente oficial de Ollama para LLM

from app.core.config import get_settings
from app.models.rag import RAGQuery, RAGResponse, RetrievedContext
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.vectorstore import VectorStoreService, get_vectorstore_service


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

# System prompt para el LLM - define su personalidad y comportamiento
# Este prompt es crítico para la calidad de las respuestas

SYSTEM_PROMPT = """You are a scientific research assistant with access to a library of academic papers.
Answer questions based on the provided context from scientific papers.
Always cite your sources by mentioning the paper title and authors.
If the context doesn't contain enough information to answer, say so clearly.
Be precise and objective in your answers, using scientific terminology appropriately.
Respond in the same language as the question."""

# ANÁLISIS DEL SYSTEM PROMPT
# ===========================
#
# Línea 1: "scientific research assistant"
# - Establece el rol experto
# - El LLM adoptará vocabulario académico
#
# Línea 2: "based on the provided context"
# - CRÍTICO: Limita al LLM a usar solo el contexto
# - Reduce alucinaciones significativamente
#
# Línea 3: "cite your sources"
# - Fuerza formato [Título - Autor] en respuestas
# - Permite verificación por el usuario
#
# Línea 4: "If context doesn't contain enough"
# - Permite al LLM decir "no sé"
# - Mejor que inventar información
#
# Línea 5: "precise and objective"
# - Evita lenguaje vago o especulativo
# - Apropiado para contexto científico
#
# Línea 6: "same language as the question"
# - Soporta multilingüe (español, inglés, etc.)
# - BGE-M3 entiende 100+ idiomas


# =============================================================================
# CLASE: RAG SERVICE
# =============================================================================

class RAGService:
    """
    Servicio RAG para Q&A sobre papers científicos.

    RESPONSABILIDADES
    =================

    1. QUERY PROCESSING:
       - Verificar caché semántico
       - Generar embedding de query
       - Recuperar chunks relevantes

    2. CONTEXT BUILDING:
       - Formatear chunks con citas
       - Respetar límite de tokens
       - Ordenar por relevancia

    3. RESPONSE GENERATION:
       - Construir prompt con contexto
       - Llamar a Ollama LLM
       - Soportar streaming

    4. CACHING:
       - Guardar respuestas en caché semántico
       - Manejar hits/misses

    USO TÍPICO
    ==========

        >>> service = get_rag_service()
        >>>
        >>> # Query simple
        >>> response = await service.query(RAGQuery(
        ...     question="¿Qué es el mecanismo de atención?"
        ... ))
        >>> print(response.answer)
        >>>
        >>> # Con streaming
        >>> async for chunk in service.query_stream(query):
        ...     print(chunk, end="", flush=True)

    Features:
    - Semantic caching: 0.95 threshold, up to 65x latency reduction
    - Retrieval caching: 30-minute TTL
    - Streaming support via Ollama
    - Multi-language support via BGE-M3
    """

    # -------------------------------------------------------------------------
    # INICIALIZACIÓN
    # -------------------------------------------------------------------------

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vectorstore_service: Optional[VectorStoreService] = None,
        llm_model: Optional[str] = None,
    ):
        """
        Inicializa el servicio RAG.

        PARÁMETROS
        ==========

        embedding_service: Servicio de embeddings
        -----------------------------------------
            Default: get_embedding_service()
            Usado para vectorizar queries

        vectorstore_service: Servicio de vector store
        ----------------------------------------------
            Default: get_vectorstore_service()
            Usado para búsqueda y caché

        llm_model: Modelo LLM a usar
        ----------------------------
            Default: settings.llm_model (llama3.1:8b)
            Alternativas: qwen2:7b, mistral:7b

        INYECCIÓN DE DEPENDENCIAS
        =========================

        Los servicios son inyectables para:
        - Testing con mocks
        - Configuración diferente por ambiente
        - Desacoplamiento

        Args:
            embedding_service: Embedding service for query encoding
            vectorstore_service: Vector store for retrieval
            llm_model: Ollama model name for generation
        """
        # Obtener configuración global
        settings = get_settings()

        # ---------------------------------------------------------------------
        # SERVICIOS INYECTABLES
        # ---------------------------------------------------------------------

        # Servicio de embeddings (para vectorizar queries)
        self._embeddings = embedding_service or get_embedding_service()

        # Servicio de vector store (para búsqueda y caché)
        self._vectorstore = vectorstore_service or get_vectorstore_service()

        # ---------------------------------------------------------------------
        # CONFIGURACIÓN DE LLM
        # ---------------------------------------------------------------------

        # Modelo LLM principal (ej: llama3.1:8b)
        self._llm_model = llm_model or settings.llm_model

        # Modelo fallback si el principal no está disponible
        self._llm_fallback = settings.llm_model_fallback

        # URL del servidor Ollama
        self._ollama_host = settings.ollama_base_url

        # ---------------------------------------------------------------------
        # CONFIGURACIÓN DE CACHÉ
        # ---------------------------------------------------------------------

        # Flag para habilitar/deshabilitar caché semántico
        self._semantic_cache_enabled = settings.semantic_cache_enabled

        # Umbral de similitud para cache hit (0.95 = muy similar)
        self._semantic_cache_threshold = settings.semantic_cache_threshold

        # ---------------------------------------------------------------------
        # CONFIGURACIÓN DE RETRIEVAL
        # ---------------------------------------------------------------------

        # Número de chunks a recuperar por defecto
        self._top_k = settings.rag_top_k

        # Límite de contexto en caracteres
        self._max_context_length = settings.rag_max_context_length

    # -------------------------------------------------------------------------
    # MÉTODOS PRIVADOS
    # -------------------------------------------------------------------------

    def _check_llm_available(self) -> str:
        """
        Verifica disponibilidad del LLM y retorna modelo disponible.

        LÓGICA
        ======

        1. Listar modelos en Ollama
        2. Verificar si el modelo principal está disponible
        3. Si no, verificar el modelo fallback
        4. Si ninguno disponible, lanzar error

        MODELOS TÍPICOS
        ===============

            ┌────────────────────────────────────────────────────────┐
            │ Modelo         │ Tamaño │ VRAM    │ Velocidad          │
            ├────────────────┼────────┼─────────┼────────────────────┤
            │ llama3.1:8b    │ 4.7GB  │ ~6GB    │ ~30 tokens/s (GPU) │
            │ qwen2:7b       │ 4.4GB  │ ~5GB    │ ~35 tokens/s (GPU) │
            │ mistral:7b     │ 4.1GB  │ ~5GB    │ ~40 tokens/s (GPU) │
            └────────────────────────────────────────────────────────┘

        Returns:
            Nombre del modelo disponible

        Raises:
            RuntimeError: Si no hay modelo disponible
        """
        try:
            # Crear cliente Ollama
            client = ollama.Client(host=self._ollama_host)

            # Listar modelos instalados
            # El cliente retorna un objeto ListResponse con atributo .models
            # Cada modelo es un objeto Model con atributo .model (nombre completo)
            response = client.list()
            available = [m.model.split(":")[0] for m in response.models]

            # Verificar modelo principal
            if self._llm_model.split(":")[0] in available:
                return self._llm_model

            # Verificar modelo fallback
            if self._llm_fallback.split(":")[0] in available:
                return self._llm_fallback

            # Ningún modelo disponible
            raise RuntimeError(
                f"No LLM model available. Run: ollama pull {self._llm_model}"
            )

        except Exception as e:
            raise RuntimeError(f"Ollama not available: {e}")

    def _build_context(
        self,
        retrieved: list[dict],
        max_length: int,
    ) -> tuple[str, list[RetrievedContext]]:
        """
        Construye el string de contexto desde chunks recuperados.

        FORMATO DE CONTEXTO
        ===================

        Cada chunk se formatea con cita:

            [Attention Is All You Need - Vaswani et al.]
            The transformer architecture relies entirely on self-attention
            mechanisms, dispensing with recurrence and convolutions entirely...

            ---

            [BERT: Pre-training of Deep Bidirectional Transformers - Devlin et al.]
            We introduce a new language representation model called BERT...

        LÍMITE DE LONGITUD
        ==================

        El contexto se trunca para respetar max_length:

            1. Agregar chunks en orden de relevancia
            2. Cuando el siguiente chunk excedería el límite, parar
            3. Chunks no incluidos se descartan

        ORDEN
        =====

        Los chunks vienen ordenados por score (relevancia):
            - Primer chunk = más relevante
            - El LLM da más peso al texto inicial del contexto

        Args:
            retrieved: Lista de chunks recuperados del vector store
            max_length: Máximo de caracteres para el contexto

        Returns:
            Tupla de (context_string, list[RetrievedContext])
        """
        contexts = []           # Lista de RetrievedContext para la respuesta
        context_parts = []      # Partes del string de contexto
        current_length = 0      # Longitud acumulada

        for r in retrieved:
            # -----------------------------------------------------------------
            # FORMATEAR CITA
            # -----------------------------------------------------------------

            # Extraer autores
            authors = r.get("authors", [])

            # Formato: "Primer Autor et al." si hay múltiples
            author_str = authors[0] if authors else "Unknown"
            if len(authors) > 1:
                author_str += " et al."

            # Construir cita: [Título - Autor]
            citation = f"[{r.get('title', 'Untitled')} - {author_str}]"

            # -----------------------------------------------------------------
            # VERIFICAR LÍMITE DE LONGITUD
            # -----------------------------------------------------------------

            text = r.get("text", "")
            entry = f"{citation}\n{text}\n"

            # ¿Añadir esta entrada excedería el límite?
            if current_length + len(entry) > max_length:
                # Parar aquí - no añadir más chunks
                break

            # Añadir al contexto
            context_parts.append(entry)
            current_length += len(entry)

            # -----------------------------------------------------------------
            # CREAR RETRIEVED CONTEXT PARA RESPUESTA
            # -----------------------------------------------------------------

            contexts.append(
                RetrievedContext(
                    paper_id=r.get("paper_id", ""),
                    chunk_index=r.get("chunk_index", 0),
                    text=text,
                    score=r.get("score", 0.0),
                    title=r.get("title", ""),
                    authors=authors,
                    year=r.get("year"),
                    doi=r.get("doi"),
                    arxiv_id=r.get("arxiv_id"),
                )
            )

        # Unir partes con separador visual
        return "\n---\n".join(context_parts), contexts

    # -------------------------------------------------------------------------
    # MÉTODOS PÚBLICOS: QUERY
    # -------------------------------------------------------------------------

    async def query(self, request: RAGQuery) -> RAGResponse:
        """
        Ejecuta query RAG completo.

        PIPELINE
        ========

            ┌─────────────────────────────────────────────────────────────┐
            │                    PIPELINE RAG QUERY                        │
            │                                                              │
            │   1. CHECK SEMANTIC CACHE                                    │
            │      │                                                       │
            │      ├─ HIT (similarity > 0.95) → Return cached response    │
            │      │                                                       │
            │      └─ MISS → Continue                                      │
            │                                                              │
            │   2. GENERATE QUERY EMBEDDING                                │
            │      query → BGE-M3 → [1024 dims]                           │
            │                                                              │
            │   3. RETRIEVE RELEVANT CHUNKS                                │
            │      vector search + filters → top-K chunks                  │
            │                                                              │
            │   4. BUILD CONTEXT                                           │
            │      chunks + citations → context string                     │
            │                                                              │
            │   5. GENERATE WITH LLM                                       │
            │      system prompt + context + question → Ollama → answer   │
            │                                                              │
            │   6. CACHE RESPONSE                                          │
            │      store in semantic cache for future queries              │
            └─────────────────────────────────────────────────────────────┘

        MÉTRICAS DE TIEMPO
        ==================

        La respuesta incluye timing detallado:
            - retrieval_time_ms: embedding + vector search
            - generation_time_ms: LLM inference
            - total_time_ms: pipeline completo

        Args:
            request: RAGQuery con pregunta y parámetros

        Returns:
            RAGResponse con respuesta, contextos y métricas
        """
        # Iniciar medición de tiempo total
        start_time = time.time()
        retrieval_time = 0.0
        generation_time = 0.0

        # ---------------------------------------------------------------------
        # PASO 1: CHECK SEMANTIC CACHE
        # ---------------------------------------------------------------------

        if request.use_semantic_cache and self._semantic_cache_enabled:
            # Buscar query similar en caché
            cached = self._vectorstore.search_semantic_cache(
                request.question,
                threshold=self._semantic_cache_threshold,
            )

            if cached:
                # ¡CACHE HIT!
                # Retornar respuesta cacheada inmediatamente
                cached_response = cached["response"]

                return RAGResponse(
                    question=request.question,
                    answer=cached_response.get("answer", ""),
                    contexts=[
                        RetrievedContext(**c) for c in cached_response.get("contexts", [])
                    ],
                    model=cached_response.get("model", self._llm_model),
                    retrieved_count=cached_response.get("retrieved_count", 0),
                    used_cache=True,  # Marcar que vino de caché
                    retrieval_time_ms=0.0,
                    generation_time_ms=0.0,
                    total_time_ms=(time.time() - start_time) * 1000,
                )

        # ---------------------------------------------------------------------
        # PASO 2: GENERATE QUERY EMBEDDING
        # ---------------------------------------------------------------------

        retrieval_start = time.time()

        # Vectorizar la pregunta con BGE-M3
        query_embedding = self._embeddings.embed_text(request.question)

        # ---------------------------------------------------------------------
        # PASO 3: RETRIEVE RELEVANT CHUNKS
        # ---------------------------------------------------------------------

        # Buscar chunks similares en LanceDB
        retrieved = self._vectorstore.search(
            query=request.question,
            top_k=request.top_k or self._top_k,
            year_min=request.year_min,
            year_max=request.year_max,
            categories=request.categories if request.categories else None,
        )

        # Medir tiempo de retrieval
        retrieval_time = (time.time() - retrieval_start) * 1000

        # ---------------------------------------------------------------------
        # PASO 4: BUILD CONTEXT
        # ---------------------------------------------------------------------

        # Construir string de contexto con citas
        # max_context_tokens * 4 ≈ caracteres (aproximación)
        context_str, contexts = self._build_context(
            retrieved,
            request.max_context_tokens * 4,
        )

        # ---------------------------------------------------------------------
        # PASO 5: GENERATE WITH LLM
        # ---------------------------------------------------------------------

        generation_start = time.time()

        # Verificar disponibilidad del modelo
        model = self._check_llm_available()

        # Construir prompt con contexto
        prompt = f"""Context from scientific papers:

{context_str}

---

Question: {request.question}

Based on the context above, provide a comprehensive answer. Cite the relevant papers."""

        # Llamar a Ollama para generar respuesta
        client = ollama.Client(host=self._ollama_host)
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": request.temperature},
        )

        # Extraer respuesta
        answer = response["message"]["content"]

        # Medir tiempo de generación
        generation_time = (time.time() - generation_start) * 1000

        # Calcular tiempo total
        total_time = (time.time() - start_time) * 1000

        # ---------------------------------------------------------------------
        # PASO 6: BUILD RESPONSE
        # ---------------------------------------------------------------------

        rag_response = RAGResponse(
            question=request.question,
            answer=answer,
            # Solo incluir contextos si se solicitaron
            contexts=contexts if request.include_sources else [],
            model=model,
            retrieved_count=len(retrieved),
            used_cache=False,
            retrieval_time_ms=retrieval_time,
            generation_time_ms=generation_time,
            total_time_ms=total_time,
            query_embedding=query_embedding,  # Para cachear después
        )

        # ---------------------------------------------------------------------
        # PASO 7: CACHE RESPONSE
        # ---------------------------------------------------------------------

        if self._semantic_cache_enabled:
            # Guardar en caché semántico para queries futuros
            self._vectorstore.add_to_semantic_cache(
                query=request.question,
                query_embedding=query_embedding,
                response={
                    "answer": answer,
                    "contexts": [c.model_dump() for c in contexts],
                    "model": model,
                    "retrieved_count": len(retrieved),
                },
            )

        return rag_response

    async def query_stream(self, request: RAGQuery):
        """
        Ejecuta query RAG con streaming de respuesta.

        STREAMING
        =========

        En lugar de esperar la respuesta completa, el LLM envía
        tokens a medida que los genera:

            Token 1: "El"
            Token 2: " mecanismo"
            Token 3: " de"
            Token 4: " atención"
            ...

        Esto permite mostrar la respuesta en tiempo real al usuario.

        USO
        ===

            async for chunk in service.query_stream(query):
                print(chunk, end="", flush=True)
            print()  # Nueva línea al final

        LIMITACIONES
        ============

        - No usa caché semántico (streaming no es cacheable fácilmente)
        - No retorna RAGResponse completo
        - Solo el texto de la respuesta

        Args:
            request: RAGQuery con pregunta y parámetros

        Yields:
            Chunks del texto de respuesta
        """
        # ---------------------------------------------------------------------
        # PASO 1: GENERATE QUERY EMBEDDING
        # ---------------------------------------------------------------------

        query_embedding = self._embeddings.embed_text(request.question)

        # ---------------------------------------------------------------------
        # PASO 2: RETRIEVE RELEVANT CHUNKS
        # ---------------------------------------------------------------------

        retrieved = self._vectorstore.search(
            query=request.question,
            top_k=request.top_k or self._top_k,
            year_min=request.year_min,
            year_max=request.year_max,
        )

        # ---------------------------------------------------------------------
        # PASO 3: BUILD CONTEXT
        # ---------------------------------------------------------------------

        context_str, contexts = self._build_context(
            retrieved,
            request.max_context_tokens * 4,
        )

        # ---------------------------------------------------------------------
        # PASO 4: STREAM RESPONSE
        # ---------------------------------------------------------------------

        model = self._check_llm_available()

        # Construir prompt
        prompt = f"""Context from scientific papers:

{context_str}

---

Question: {request.question}

Based on the context above, provide a comprehensive answer. Cite the relevant papers."""

        # Cliente Ollama
        client = ollama.Client(host=self._ollama_host)

        # Llamar con stream=True para obtener generador
        for chunk in client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": request.temperature},
            stream=True,  # Habilitar streaming
        ):
            # Yield cada chunk de texto
            yield chunk["message"]["content"]

    # -------------------------------------------------------------------------
    # MÉTODOS PÚBLICOS: BÚSQUEDA SIMPLE
    # -------------------------------------------------------------------------

    def search_papers(
        self,
        query: str,
        top_k: int = 10,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
    ) -> list[dict]:
        """
        Busca papers relevantes sin generar respuesta.

        CUÁNDO USAR
        ===========

        Útil cuando solo se necesita encontrar papers:
        - Exploración del corpus
        - UI de búsqueda
        - Sin necesidad de LLM

        DIFERENCIA CON QUERY()
        ======================

            search_papers():
            - Solo retrieval
            - Sin LLM
            - Rápido (~100ms)
            - Retorna chunks

            query():
            - Retrieval + LLM
            - Respuesta en lenguaje natural
            - Más lento (~3000ms)
            - Retorna RAGResponse

        Args:
            query: Texto de búsqueda
            top_k: Número de resultados
            year_min: Filtro año mínimo
            year_max: Filtro año máximo

        Returns:
            Lista de chunks coincidentes
        """
        return self._vectorstore.search(
            query=query,
            top_k=top_k,
            year_min=year_min,
            year_max=year_max,
        )


# =============================================================================
# SINGLETON: GET RAG SERVICE
# =============================================================================

@lru_cache
def get_rag_service() -> RAGService:
    """
    Obtiene instancia singleton del servicio RAG.

    ¿POR QUÉ SINGLETON?
    ===================

    1. SERVICIOS COMPARTIDOS: Usa los mismos embeddings/vectorstore
    2. CONFIGURACIÓN: Consistente en toda la aplicación
    3. CACHÉ: Comparte caché semántico

    USO
    ===

        service = get_rag_service()
        response = await service.query(RAGQuery(question="..."))

    Returns:
        Instancia singleton de RAGService
    """
    return RAGService()
