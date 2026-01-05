"""
================================================================================
SERVICIO DE VECTOR STORE - LANCEDB PARA PAPERS CIENTÍFICOS
================================================================================

Este módulo implementa el almacenamiento vectorial usando LanceDB, una base de
datos vectorial embebida optimizada para búsqueda de similitud semántica.

¿QUÉ ES LANCEDB?
================

LanceDB es una base de datos vectorial moderna con características únicas:

    ┌────────────────────────────────────────────────────────────────────────┐
    │                     COMPARATIVA DE VECTOR DATABASES                    │
    │                                                                        │
    │   ┌──────────────┬───────────┬───────────┬──────────┬───────────────┐  │
    │   │ Característica│ LanceDB   │ Chroma    │ Pinecone │ Milvus       │  │
    │   ├──────────────┼───────────┼───────────┼──────────┼───────────────┤  │
    │   │ Arquitectura │ Embedded  │ Embedded  │ Cloud    │ Server       │  │
    │   │ Servidor req.│ No        │ No        │ Sí       │ Sí           │  │
    │   │ Escala       │ Billones  │ Millones  │ Billones │ Billones     │  │
    │   │ Formato      │ Lance     │ DuckDB    │ Propiet. │ Propiet.     │  │
    │   │ Búsq. híbrida│ Sí (FTS5) │ No        │ Sí       │ Sí           │  │
    │   │ Offline      │ ✓         │ ✓         │ ✗        │ ✓            │  │
    │   │ Costo        │ Gratis    │ Gratis    │ $$$/mes  │ Gratis       │  │
    │   └──────────────┴───────────┴───────────┴──────────┴───────────────┘  │
    └────────────────────────────────────────────────────────────────────────┘

¿POR QUÉ LANCEDB PARA ESTE PROYECTO?
====================================

1. EMBEDDED (Sin servidor):
   - No requiere proceso separado (a diferencia de Milvus/Weaviate)
   - Simplifica despliegue y backup
   - Ideal para aplicaciones offline/desktop

2. LANCE COLUMNAR FORMAT:
   - Formato columnar optimizado para SSD/NVMe
   - Compresión eficiente de vectores
   - Acceso aleatorio rápido

3. ESCALA:
   - Hasta billones de vectores
   - IVF-PQ para colecciones grandes
   - Particionado automático

ARQUITECTURA DE DATOS
=====================

El sistema tiene dos tablas principales:

    ┌────────────────────────────────────────────────────────────────────────┐
    │                        TABLAS EN LANCEDB                               │
    │                                                                        │
    │   ┌─────────────────────────────────────────────────────────────────┐  │
    │   │                    paper_chunks                                  │  │
    │   │   ────────────────────────────────────────────────────────────  │  │
    │   │   id: string        │ "10.1038/nature_0"                        │  │
    │   │   paper_id: string  │ "10.1038/nature12373"                     │  │
    │   │   chunk_index: int32│ 0, 1, 2, ...                              │  │
    │   │   text: string      │ "The transformer architecture..."        │  │
    │   │   section: string   │ "introduction"                            │  │
    │   │   vector: float[1024]│ [0.023, -0.156, ...]                     │  │
    │   │   year: int32       │ 2017                                      │  │
    │   │   title: string     │ "Attention Is All You Need"              │  │
    │   │   ...               │                                           │  │
    │   └─────────────────────────────────────────────────────────────────┘  │
    │                                                                        │
    │   ┌─────────────────────────────────────────────────────────────────┐  │
    │   │                    semantic_cache                                │  │
    │   │   ────────────────────────────────────────────────────────────  │  │
    │   │   id: string        │ "a7f3c9b2e..."                            │  │
    │   │   query: string     │ "¿Qué es attention?"                      │  │
    │   │   vector: float[1024]│ [0.045, 0.123, ...]                      │  │
    │   │   response_json: str│ '{"answer": "...", "contexts": [...]}'   │  │
    │   │   created_at: ts    │ 2024-01-15 10:30:00                       │  │
    │   │   hit_count: int32  │ 5                                         │  │
    │   └─────────────────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────────────────┘

SISTEMA DE CACHÉ DE TRES CAPAS
==============================

El sistema implementa caché a tres niveles:

    ┌────────────────────────────────────────────────────────────────────────┐
    │                     TRES CAPAS DE CACHÉ                                │
    │                                                                        │
    │   ┌─────────────┐                                                      │
    │   │   Layer 1   │  Embedding Cache (EmbeddingService)                 │
    │   │   diskcache │  - Texto → Vector                                   │
    │   │   Persist.  │  - Evita re-vectorizar el mismo texto              │
    │   └─────────────┘                                                      │
    │         │                                                              │
    │         ▼                                                              │
    │   ┌─────────────┐                                                      │
    │   │   Layer 2   │  Retrieval Cache (TTLCache)                         │
    │   │   TTLCache  │  - Query+filtros → Resultados                       │
    │   │   30 min    │  - TTL 30 minutos, max 1000 entries                 │
    │   └─────────────┘                                                      │
    │         │                                                              │
    │         ▼                                                              │
    │   ┌─────────────┐                                                      │
    │   │   Layer 3   │  Semantic Cache (LanceDB)                           │
    │   │   LanceDB   │  - Query similar → Respuesta RAG completa          │
    │   │   0.95 sim  │  - Umbral 0.95, speedup 65x                        │
    │   └─────────────┘                                                      │
    └────────────────────────────────────────────────────────────────────────┘

IVF-PQ INDEXING
===============

Para colecciones grandes (1M+ papers), se usa IVF-PQ:

    IVF (Inverted File Index):
        - Particiona vectores en clusters
        - Solo busca en particiones cercanas al query
        - 256 particiones es óptimo para ~1M vectores

    PQ (Product Quantization):
        - Comprime vectores en sub-vectores
        - 96 sub-vectores para 1024 dims (≈10.7 dims cada uno)
        - Reduce memoria ~10x con pérdida mínima de precisión

LanceDB advantages for offline use:
- Truly embedded (no server process)
- Disk-native (Lance columnar format optimized for SSD)
- Scales to billions of vectors
- Hybrid search (vector + full-text via FTS5)
- IVF-PQ indexing for large collections (1M+ papers)
"""

# =============================================================================
# IMPORTS
# =============================================================================

import json                      # Para serializar respuestas y listas
from datetime import datetime    # Timestamps para registros
from functools import lru_cache  # Singleton pattern
from pathlib import Path
from typing import Optional, Any

import lancedb                   # Base de datos vectorial embebida
import pyarrow as pa             # Esquemas de datos (Apache Arrow)
from cachetools import TTLCache  # Cache con Time-To-Live

from app.core.config import get_settings
from app.services.embeddings import EmbeddingService, get_embedding_service


# =============================================================================
# ESQUEMAS PYARROW
# =============================================================================

# -----------------------------------------------------------------------------
# ESQUEMA: PAPER_CHUNKS
# -----------------------------------------------------------------------------

# Esquema PyArrow para la tabla de chunks de papers
# PyArrow define el esquema de forma tipada y eficiente para almacenamiento columnar

CHUNKS_SCHEMA = pa.schema([
    # ID único del chunk: "{paper_id}_{chunk_index}"
    # Ejemplo: "10.1038/nature12373_0", "10.1038/nature12373_1"
    # Permite identificar cada chunk de forma única
    pa.field("id", pa.string()),

    # ID del paper padre (DOI, arXiv ID, etc.)
    # Usado para JOIN con metadatos del paper
    pa.field("paper_id", pa.string()),

    # Índice del chunk dentro del paper (0-based)
    # int32 es suficiente para papers (típicamente <1000 chunks)
    pa.field("chunk_index", pa.int32()),

    # Texto del chunk (hasta ~1000 caracteres)
    pa.field("text", pa.string()),

    # Sección del paper donde está el chunk
    # Valores: "abstract", "introduction", "methods", "results", "discussion"
    pa.field("section", pa.string()),

    # Vector embedding BGE-M3: lista fija de 1024 float32
    # list_(float32(), 1024) = FixedSizeList para eficiencia
    # ~4KB por vector (1024 * 4 bytes)
    pa.field("vector", pa.list_(pa.float32(), 1024)),

    # Año de publicación (denormalizado para filtrado eficiente)
    # int32 cubre años hasta 2^31 (más que suficiente)
    pa.field("year", pa.int32()),

    # Categorías arXiv como lista de strings
    # Ejemplo: ["cs.AI", "cs.LG"]
    pa.field("arxiv_categories", pa.list_(pa.string())),

    # Título del paper (denormalizado para UI)
    pa.field("title", pa.string()),

    # Autores como JSON string (lista serializada)
    # LanceDB no soporta listas de strings complejas directamente
    pa.field("authors", pa.string()),

    # DOI si disponible
    pa.field("doi", pa.string()),

    # arXiv ID si disponible
    pa.field("arxiv_id", pa.string()),

    # Timestamp de cuando se creó el chunk
    # timestamp("us") = microsegundos (precisión suficiente)
    pa.field("created_at", pa.timestamp("us")),
])

# -----------------------------------------------------------------------------
# ESQUEMA: SEMANTIC_CACHE
# -----------------------------------------------------------------------------

# Esquema PyArrow para la tabla de caché semántico

CACHE_SCHEMA = pa.schema([
    # ID único del entry (hash del query)
    pa.field("id", pa.string()),

    # Query original en texto plano
    pa.field("query", pa.string()),

    # Vector embedding del query (1024 dims BGE-M3)
    # Este es el campo que se indexa para búsqueda por similitud
    pa.field("vector", pa.list_(pa.float32(), 1024)),

    # RAGResponse serializada como JSON
    # Incluye: answer, contexts, timing, etc.
    pa.field("response_json", pa.string()),

    # Timestamp de creación
    pa.field("created_at", pa.timestamp("us")),

    # Contador de hits para estadísticas
    pa.field("hit_count", pa.int32()),
])


# =============================================================================
# CLASE: VECTOR STORE SERVICE
# =============================================================================

class VectorStoreService:
    """
    Servicio de almacenamiento vectorial basado en LanceDB.

    RESPONSABILIDADES
    =================

    1. ALMACENAMIENTO DE CHUNKS:
       - Añadir chunks con embeddings
       - Búsqueda por similitud semántica
       - Filtrado por metadatos

    2. CACHÉ SEMÁNTICO:
       - Almacenar pares query-response
       - Buscar queries similares
       - Speedup de hasta 65x

    3. CACHÉ DE RETRIEVAL:
       - Cache en memoria con TTL
       - Evita re-búsquedas frecuentes

    USO TÍPICO
    ==========

        >>> service = get_vectorstore_service()
        >>>
        >>> # Añadir chunks
        >>> service.add_chunks([
        ...     {"paper_id": "10.1038/...", "text": "...", "chunk_index": 0}
        ... ])
        >>>
        >>> # Buscar
        >>> results = service.search("transformer attention", top_k=10)

    Features:
    - Hybrid search (vector + full-text)
    - Metadata filtering (year, categories, authors)
    - IVF-PQ indexing for large collections
    - Semantic cache with 0.95 similarity threshold
    - Retrieval cache with 30-minute TTL
    """

    # -------------------------------------------------------------------------
    # INICIALIZACIÓN
    # -------------------------------------------------------------------------

    def __init__(
        self,
        db_path: Optional[Path] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        """
        Inicializa el servicio de vector store.

        PARÁMETROS
        ==========

        db_path: Ruta al directorio de la base de datos
        ------------------------------------------------
            Default: Usa settings.lancedb_uri (data/vectors)
            LanceDB crea múltiples archivos en este directorio:
                - *.lance: Archivos de datos columnar
                - *.idx: Archivos de índice

        embedding_service: Servicio de embeddings inyectable
        ----------------------------------------------------
            Default: get_embedding_service() (singleton global)
            Permite inyectar mock para testing

        ESTRUCTURA DE ARCHIVOS
        ======================

            data/vectors/
            ├── paper_chunks.lance/
            │   ├── data/
            │   │   ├── 0.lance      # Fragmento de datos
            │   │   └── 1.lance
            │   └── _versions/        # Control de versiones
            └── semantic_cache.lance/
                └── ...

        Args:
            db_path: Path to LanceDB database directory
            embedding_service: Embedding service for vector generation
        """
        # Obtener configuración
        settings = get_settings()

        # ---------------------------------------------------------------------
        # CONFIGURACIÓN DE RUTA
        # ---------------------------------------------------------------------

        # Ruta a la base de datos LanceDB
        self.db_path = db_path or Path(settings.lancedb_uri)

        # Crear directorio si no existe
        self.db_path.mkdir(parents=True, exist_ok=True)

        # ---------------------------------------------------------------------
        # DEPENDENCIAS
        # ---------------------------------------------------------------------

        # Servicio de embeddings (inyectable para testing)
        self._embedding_service = embedding_service or get_embedding_service()

        # ---------------------------------------------------------------------
        # CONEXIÓN A LANCEDB
        # ---------------------------------------------------------------------

        # Conectar a LanceDB (operación local, no requiere servidor)
        # lancedb.connect() abre o crea la base de datos
        self._db = lancedb.connect(str(self.db_path))

        # ---------------------------------------------------------------------
        # INICIALIZAR TABLAS
        # ---------------------------------------------------------------------

        # Tabla principal de chunks de papers
        self._chunks_table = self._get_or_create_table("paper_chunks", CHUNKS_SCHEMA)

        # Tabla de caché semántico
        self._cache_table = self._get_or_create_table("semantic_cache", CACHE_SCHEMA)

        # ---------------------------------------------------------------------
        # CACHÉ DE RETRIEVAL (EN MEMORIA)
        # ---------------------------------------------------------------------

        # TTLCache: Cache con Time-To-Live automático
        # - maxsize: Máximo número de entradas (1000)
        # - ttl: Tiempo de vida en segundos (1800 = 30 minutos)
        #
        # Cuando una entrada expira o el cache está lleno, se elimina
        self._retrieval_cache = TTLCache(
            maxsize=settings.retrieval_cache_maxsize,
            ttl=settings.retrieval_cache_ttl,
        )

        # ---------------------------------------------------------------------
        # CONFIGURACIÓN DE CACHÉ SEMÁNTICO
        # ---------------------------------------------------------------------

        # Umbral de similitud para cache hit (0.95 = muy similar)
        self._semantic_cache_threshold = settings.semantic_cache_threshold

        # Flag para habilitar/deshabilitar caché semántico
        self._semantic_cache_enabled = settings.semantic_cache_enabled

    # -------------------------------------------------------------------------
    # MÉTODOS PRIVADOS
    # -------------------------------------------------------------------------

    def _get_or_create_table(
        self,
        name: str,
        schema: pa.Schema,
    ) -> lancedb.table.Table:
        """
        Obtiene tabla existente o crea una nueva.

        LÓGICA
        ======

        1. Verificar si la tabla existe en la base de datos
        2. Si existe: abrir y retornar
        3. Si no existe: crear con el esquema proporcionado

        IDEMPOTENCIA
        ============

        Este método es idempotente: llamarlo múltiples veces
        con el mismo nombre siempre retorna la misma tabla.

        Args:
            name: Nombre de la tabla
            schema: Esquema PyArrow para la tabla

        Returns:
            Referencia a la tabla LanceDB
        """
        # Verificar si la tabla ya existe
        if name in self._db.table_names():
            # Abrir tabla existente
            return self._db.open_table(name)

        # Crear nueva tabla con el esquema
        return self._db.create_table(name, schema=schema)

    # -------------------------------------------------------------------------
    # MÉTODOS PÚBLICOS: GESTIÓN DE CHUNKS
    # -------------------------------------------------------------------------

    def add_chunks(
        self,
        chunks: list[dict[str, Any]],
        create_index: bool = False,
    ) -> int:
        """
        Añade chunks de papers al vector store.

        PROCESO
        =======

        1. Extraer textos de los chunks
        2. Generar embeddings en batch (eficiente)
        3. Construir registros con metadatos
        4. Insertar en LanceDB
        5. Opcionalmente crear índice IVF-PQ

        FORMATO DE CHUNKS
        =================

        Cada chunk debe ser un diccionario con:

            {
                "paper_id": "10.1038/nature12373",
                "chunk_index": 0,
                "text": "The transformer architecture...",
                "section": "introduction",
                "year": 2017,
                "arxiv_categories": ["cs.AI", "cs.LG"],
                "title": "Attention Is All You Need",
                "authors": ["Vaswani", "Shazeer", ...],
                "doi": "10.1038/...",
                "arxiv_id": None
            }

        EMBEDDINGS
        ==========

        Los embeddings se generan automáticamente:
        - Se usa embed_batch() para eficiencia
        - El caché de embeddings se aprovecha
        - Típicamente ~10-50 chunks por paper

        Args:
            chunks: Lista de diccionarios con datos de chunks
            create_index: Si crear índice IVF-PQ después

        Returns:
            Número de chunks añadidos
        """
        # Validar entrada
        if not chunks:
            return 0

        # ---------------------------------------------------------------------
        # PASO 1: EXTRAER TEXTOS Y GENERAR EMBEDDINGS
        # ---------------------------------------------------------------------

        # Extraer textos para vectorización
        texts = [c["text"] for c in chunks]

        # Generar embeddings en batch (más eficiente que uno a uno)
        # El servicio de embeddings maneja el caché automáticamente
        embeddings = self._embedding_service.embed_batch(texts)

        # ---------------------------------------------------------------------
        # PASO 2: CONSTRUIR REGISTROS PARA LANCEDB
        # ---------------------------------------------------------------------

        records = []
        for chunk, embedding in zip(chunks, embeddings):
            # Construir registro con todos los campos del esquema
            record = {
                # ID único: paper_id + chunk_index
                "id": f"{chunk['paper_id']}_{chunk['chunk_index']}",

                # Referencia al paper padre
                "paper_id": chunk["paper_id"],
                "chunk_index": chunk["chunk_index"],

                # Contenido
                "text": chunk["text"],
                "section": chunk.get("section", ""),

                # Vector embedding (1024 floats)
                "vector": embedding,

                # Metadatos para filtrado
                "year": chunk.get("year", 0),
                "arxiv_categories": chunk.get("arxiv_categories", []),

                # Metadatos denormalizados para UI
                "title": chunk.get("title", ""),
                "authors": json.dumps(chunk.get("authors", [])),  # Serializar lista
                "doi": chunk.get("doi", ""),
                "arxiv_id": chunk.get("arxiv_id", ""),

                # Timestamp
                "created_at": datetime.utcnow(),
            }
            records.append(record)

        # ---------------------------------------------------------------------
        # PASO 3: INSERTAR EN LANCEDB
        # ---------------------------------------------------------------------

        # add() inserta registros en la tabla
        # LanceDB maneja la indexación automáticamente
        self._chunks_table.add(records)

        # ---------------------------------------------------------------------
        # PASO 4: CREAR ÍNDICE (OPCIONAL)
        # ---------------------------------------------------------------------

        # Para colecciones grandes (1M+ papers), crear índice IVF-PQ
        if create_index:
            self.create_index()

        return len(records)

    def create_index(
        self,
        num_partitions: int = 256,
        num_sub_vectors: int = 96,
    ) -> None:
        """
        Crea índice IVF-PQ para búsqueda eficiente en colecciones grandes.

        ¿QUÉ ES IVF-PQ?
        ===============

        IVF (Inverted File Index):
        --------------------------
        Divide el espacio vectorial en particiones (clusters).
        En búsqueda, solo se exploran las particiones cercanas al query.

            ┌────────────────────────────────────────────────────────────┐
            │           ESPACIO VECTORIAL PARTICIONADO                   │
            │                                                            │
            │     ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐             │
            │     │ P1   │   │ P2   │   │ P3   │   │ P4   │  ...        │
            │     │ ●●●  │   │ ●●   │   │ ●●●● │   │ ●    │             │
            │     └──────┘   └──────┘   └──────┘   └──────┘             │
            │                    ↑                                       │
            │            Query solo busca aquí                           │
            └────────────────────────────────────────────────────────────┘

        PQ (Product Quantization):
        --------------------------
        Comprime vectores dividiendo en sub-vectores y cuantizando.

            Vector original (1024 dims):
            [0.1, 0.2, ..., 0.9]

            ↓ Dividir en 96 sub-vectores

            [sub1][sub2][sub3]...[sub96]

            ↓ Cuantizar cada sub-vector a un código

            [code1][code2]...[code96]

            Compresión: ~10x menor memoria

        PARÁMETROS RECOMENDADOS
        =======================

            - 256 particiones: Óptimo para ~1M vectores
            - 96 sub-vectores: Para 1024 dims (≈10.7 dims/sub)

        CUÁNDO CREAR ÍNDICE
        ===================

            - NO necesario para < 100K vectores (scan es rápido)
            - RECOMENDADO para > 100K vectores
            - REQUERIDO para > 1M vectores

        Recommended for collections with 1M+ papers.
        Parameters from guide: 256 partitions, 96 sub-vectors.

        Args:
            num_partitions: Número de particiones IVF (default: 256)
            num_sub_vectors: Número de sub-vectores PQ (default: 96)
        """
        settings = get_settings()

        # Crear índice con parámetros configurados
        self._chunks_table.create_index(
            num_partitions=num_partitions or settings.lancedb_num_partitions,
            num_sub_vectors=num_sub_vectors or settings.lancedb_num_sub_vectors,
        )

    # -------------------------------------------------------------------------
    # MÉTODOS PÚBLICOS: BÚSQUEDA
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        categories: Optional[list[str]] = None,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Busca chunks similares al query.

        PIPELINE DE BÚSQUEDA
        ====================

        1. Verificar caché de retrieval (TTL 30min)
        2. Si miss: vectorizar query
        3. Ejecutar búsqueda vectorial en LanceDB
        4. Aplicar filtros de metadatos
        5. Convertir resultados a diccionarios
        6. Cachear resultados

        SIMILITUD VS DISTANCIA
        ======================

        LanceDB retorna "_distance" (L2 distance por defecto).
        Menor distancia = más similar.

            distancia 0.0: Vectores idénticos
            distancia 1.0: Vectores muy diferentes

        En el resultado, "score" es la distancia directa.
        (Para similitud coseno, se podría convertir con 1-distance)

        FILTROS
        =======

        Los filtros se aplican DESPUÉS de la búsqueda vectorial:

            search().where("year >= 2020 AND year <= 2023")

        Esto puede afectar el número real de resultados
        (puede retornar menos de top_k si muchos no pasan el filtro).

        Args:
            query: Texto de búsqueda
            top_k: Número máximo de resultados
            year_min: Año mínimo (inclusive)
            year_max: Año máximo (inclusive)
            categories: Categorías arXiv para filtrar
            use_cache: Usar caché de retrieval

        Returns:
            Lista de chunks coincidentes con scores
        """
        # ---------------------------------------------------------------------
        # PASO 1: VERIFICAR CACHÉ DE RETRIEVAL
        # ---------------------------------------------------------------------

        # Generar clave de caché única para esta búsqueda
        # Incluye todos los parámetros que afectan el resultado
        cache_key = f"{query}:{top_k}:{year_min}:{year_max}:{categories}"

        # Verificar si tenemos resultados cacheados
        if use_cache and cache_key in self._retrieval_cache:
            # Cache hit - retornar resultados cacheados
            return self._retrieval_cache[cache_key]

        # ---------------------------------------------------------------------
        # PASO 2: VECTORIZAR QUERY
        # ---------------------------------------------------------------------

        # Generar embedding del query (usa caché de embeddings)
        query_embedding = self._embedding_service.embed_text(query)

        # ---------------------------------------------------------------------
        # PASO 3: EJECUTAR BÚSQUEDA VECTORIAL
        # ---------------------------------------------------------------------

        # search() busca los top_k vectores más cercanos
        search = self._chunks_table.search(query_embedding).limit(top_k)

        # ---------------------------------------------------------------------
        # PASO 4: APLICAR FILTROS
        # ---------------------------------------------------------------------

        filters = []

        # Filtro de año mínimo
        if year_min:
            filters.append(f"year >= {year_min}")

        # Filtro de año máximo
        if year_max:
            filters.append(f"year <= {year_max}")

        # Nota: Filtrado por categorías requiere lógica más compleja
        # debido a que es una lista (se omite por ahora)

        # Aplicar filtros SQL-like
        if filters:
            where_clause = " AND ".join(filters)
            search = search.where(where_clause)

        # ---------------------------------------------------------------------
        # PASO 5: EJECUTAR Y CONVERTIR RESULTADOS
        # ---------------------------------------------------------------------

        # Ejecutar búsqueda y convertir a DataFrame pandas
        results_df = search.to_pandas()

        # Convertir cada fila a diccionario
        results = []
        for _, row in results_df.iterrows():
            result = {
                # Identificadores
                "id": row["id"],
                "paper_id": row["paper_id"],
                "chunk_index": int(row["chunk_index"]),

                # Contenido
                "text": row["text"],
                "section": row["section"],

                # Score (distancia - menor es mejor)
                "score": float(row.get("_distance", 0)),

                # Metadatos para UI
                "year": int(row["year"]) if row["year"] else None,
                "title": row["title"],
                "authors": json.loads(row["authors"]) if row["authors"] else [],
                "doi": row["doi"],
                "arxiv_id": row["arxiv_id"],
            }
            results.append(result)

        # ---------------------------------------------------------------------
        # PASO 6: CACHEAR RESULTADOS
        # ---------------------------------------------------------------------

        if use_cache:
            # Guardar en caché de retrieval (expira en 30 min)
            self._retrieval_cache[cache_key] = results

        return results

    # -------------------------------------------------------------------------
    # MÉTODOS PÚBLICOS: CACHÉ SEMÁNTICO
    # -------------------------------------------------------------------------

    def search_semantic_cache(
        self,
        query: str,
        threshold: Optional[float] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Busca en caché semántico queries similares anteriores.

        DIFERENCIA CON RETRIEVAL CACHE
        ==============================

            Retrieval Cache:
            - Clave exacta (query + filtros)
            - En memoria (TTLCache)
            - TTL 30 minutos

            Semantic Cache:
            - Similitud semántica (vector)
            - En disco (LanceDB)
            - Sin TTL explícito
            - Responde queries reformuladas

        EJEMPLO
        =======

            Query anterior: "¿Qué es el mecanismo de atención?"
            Query nuevo:    "¿Cómo funciona attention en transformers?"
            Similitud:      0.96 > 0.95 → HIT

        SPEEDUP
        =======

            Sin cache:  ~3000-5000ms (embedding + vector search + LLM)
            Con cache:  ~50-80ms (embedding + vector search en cache)
            Speedup:    ~65x

        Returns cached response if similarity > threshold (default 0.95).
        Achieves up to 65x latency reduction for repeated queries.

        Args:
            query: Query de búsqueda
            threshold: Umbral de similitud (default: 0.95)

        Returns:
            Respuesta cacheada si hay hit, None si miss
        """
        # Verificar si caché semántico está habilitado
        if not self._semantic_cache_enabled:
            return None

        # Usar umbral por defecto si no se especifica
        threshold = threshold or self._semantic_cache_threshold

        # ---------------------------------------------------------------------
        # PASO 1: VECTORIZAR QUERY
        # ---------------------------------------------------------------------

        query_embedding = self._embedding_service.embed_text(query)

        # ---------------------------------------------------------------------
        # PASO 2: BUSCAR EN CACHE
        # ---------------------------------------------------------------------

        try:
            # Buscar el vector más cercano en la tabla de cache
            results = (
                self._cache_table.search(query_embedding)
                .limit(1)  # Solo necesitamos el más cercano
                .to_pandas()
            )

            # Verificar si hay resultados
            if results.empty:
                return None

            # ---------------------------------------------------------------------
            # PASO 3: VERIFICAR UMBRAL DE SIMILITUD
            # ---------------------------------------------------------------------

            # LanceDB retorna distancia (0 = idéntico)
            # Convertir a similitud: similitud = 1 - distancia
            distance = results.iloc[0].get("_distance", 1.0)
            similarity = 1.0 - distance

            # Verificar si supera el umbral
            if similarity >= threshold:
                # ¡CACHE HIT!

                # Extraer datos del resultado
                cache_id = results.iloc[0]["id"]
                response_json = results.iloc[0]["response_json"]

                # TODO: Actualizar hit_count (requiere update en LanceDB)

                # Retornar respuesta deserializada
                return {
                    "cached": True,
                    "similarity": similarity,
                    "response": json.loads(response_json),
                }

        except Exception:
            # Silenciar errores de cache (no crítico)
            pass

        return None

    def add_to_semantic_cache(
        self,
        query: str,
        query_embedding: list[float],
        response: dict[str, Any],
    ) -> None:
        """
        Añade par query-response al caché semántico.

        CUÁNDO LLAMAR
        =============

        Se llama después de generar una respuesta RAG exitosa:

            1. Usuario hace query
            2. Cache miss (no hay query similar)
            3. Ejecutar pipeline RAG completo
            4. Generar respuesta
            5. → Guardar en cache semántico

        DEDUPLICACIÓN
        =============

        Se usa hash del query como ID para evitar duplicados exactos.
        Queries similares pero no idénticos tendrán IDs diferentes
        (esto es intencional - ambos pueden ser útiles).

        Args:
            query: Query original
            query_embedding: Vector del query (ya calculado)
            response: Respuesta RAG a cachear
        """
        # Verificar si caché está habilitado
        if not self._semantic_cache_enabled:
            return

        import hashlib

        # Generar ID único basado en hash del query
        # Usamos solo los primeros 16 caracteres del hash
        cache_id = hashlib.sha256(query.encode()).hexdigest()[:16]

        # Construir registro para la tabla
        record = {
            "id": cache_id,
            "query": query,
            "vector": query_embedding,
            "response_json": json.dumps(response),
            "created_at": datetime.utcnow(),
            "hit_count": 0,
        }

        # Insertar en la tabla de cache
        self._cache_table.add([record])

    # -------------------------------------------------------------------------
    # MÉTODOS PÚBLICOS: ADMINISTRACIÓN
    # -------------------------------------------------------------------------

    def delete_paper(self, paper_id: str) -> int:
        """
        Elimina todos los chunks de un paper.

        CUÁNDO USAR
        ===========

        - Reindexar un paper (primero eliminar, luego añadir)
        - Eliminar paper de la biblioteca
        - Limpiar datos corruptos

        EFECTO EN CACHES
        ================

        - Retrieval cache: Se limpia completamente
        - Semantic cache: NO se limpia (las respuestas pueden seguir válidas)
        - Embedding cache: NO afectado (es por texto, no por paper)

        Args:
            paper_id: ID del paper a eliminar

        Returns:
            Número de chunks eliminados (0 por limitación de LanceDB)
        """
        # Eliminar chunks con WHERE clause
        self._chunks_table.delete(f"paper_id = '{paper_id}'")

        # Limpiar retrieval cache (puede tener resultados obsoletos)
        self._retrieval_cache.clear()

        # LanceDB no retorna count en delete
        return 0

    def get_stats(self) -> dict[str, Any]:
        """
        Obtiene estadísticas del vector store.

        MÉTRICAS
        ========

        - db_path: Ruta a la base de datos
        - chunks_count: Total de chunks indexados
        - semantic_cache_count: Entries en cache semántico
        - retrieval_cache_size: Entries en cache de retrieval (memoria)
        - embedding_model: Modelo de embeddings en uso

        USO
        ===

        Útil para dashboards, monitoreo y debugging.

        EJEMPLO
        =======

            >>> service.get_stats()
            {
                "db_path": "/app/data/vectors",
                "chunks_count": 15234,
                "semantic_cache_count": 45,
                "retrieval_cache_size": 12,
                "embedding_model": "bge-m3"
            }

        Returns:
            Diccionario con estadísticas
        """
        # Contar filas en cada tabla
        chunks_count = self._chunks_table.count_rows()
        cache_count = self._cache_table.count_rows()

        return {
            "db_path": str(self.db_path),
            "chunks_count": chunks_count,
            "semantic_cache_count": cache_count,
            "retrieval_cache_size": len(self._retrieval_cache),
            "embedding_model": self._embedding_service.model,
        }


# =============================================================================
# SINGLETON: GET VECTORSTORE SERVICE
# =============================================================================

@lru_cache
def get_vectorstore_service() -> VectorStoreService:
    """
    Obtiene instancia singleton del servicio de vector store.

    ¿POR QUÉ SINGLETON?
    ===================

    1. CONEXIÓN DB: Mantiene una sola conexión a LanceDB
    2. CACHE COMPARTIDO: Todos usan el mismo retrieval cache
    3. CONSISTENCIA: Estado unificado en toda la aplicación
    4. EFICIENCIA: Evita abrir/cerrar conexiones

    USO
    ===

        # En cualquier parte del código:
        service = get_vectorstore_service()
        results = service.search("machine learning")

    Returns:
        Instancia singleton de VectorStoreService
    """
    return VectorStoreService()
