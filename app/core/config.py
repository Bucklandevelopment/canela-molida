"""
=============================================================================
MÓDULO DE CONFIGURACIÓN CENTRALIZADA - Scientific Library RAG
=============================================================================

Este módulo implementa el patrón "Configuration as Code" usando Pydantic Settings,
proporcionando una única fuente de verdad para toda la configuración de la aplicación.

CONCEPTOS CLAVE IMPLEMENTADOS:
------------------------------
1. PYDANTIC SETTINGS: Framework que combina validación de tipos con carga de
   variables de entorno. Garantiza que la configuración sea correcta en tiempo
   de carga, no en tiempo de ejecución (fail-fast principle).

2. SINGLETON PATTERN via @lru_cache: Asegura que solo exista una instancia de
   Settings en toda la aplicación, evitando inconsistencias y reduciendo overhead.

3. TWELVE-FACTOR APP: Sigue el principio de configuración vía entorno, permitiendo
   que la misma base de código funcione en desarrollo, staging y producción sin
   modificaciones.

4. VALORES POR DEFECTO SENSATOS: Cada parámetro tiene un default que funciona
   "out of the box" para desarrollo local, pero puede sobrescribirse en producción.

ARQUITECTURA DE CACHÉ (Tres Niveles):
------------------------------------
El sistema RAG implementa tres capas de caché para optimizar rendimiento:

┌─────────────────────────────────────────────────────────────────────────────┐
│  CAPA 1: EMBEDDING CACHE (Persistente en disco)                             │
│  ├── Almacena: vectores de embeddings calculados                            │
│  ├── Beneficio: Evita re-computar embeddings para textos ya procesados      │
│  ├── Implementación: diskcache + CacheBackedEmbeddings pattern              │
│  └── Reducción de latencia: ~100x para documentos ya indexados              │
├─────────────────────────────────────────────────────────────────────────────┤
│  CAPA 2: RETRIEVAL CACHE (En memoria, TTL 30 min)                           │
│  ├── Almacena: resultados de búsquedas vectoriales                          │
│  ├── Beneficio: Queries repetidas son instantáneas                          │
│  ├── Implementación: cachetools.TTLCache                                    │
│  └── TTL: 30 minutos (balanceo entre frescura y rendimiento)                │
├─────────────────────────────────────────────────────────────────────────────┤
│  CAPA 3: SEMANTIC CACHE (Vectorial, umbral 0.95)                            │
│  ├── Almacena: pares (query_embedding, response) en LanceDB                 │
│  ├── Beneficio: Queries SIMILARES (no idénticas) retornan respuestas cached │
│  ├── Threshold: 0.95 cosine similarity                                      │
│  └── Reducción de latencia: hasta 65x según benchmarks                      │
└─────────────────────────────────────────────────────────────────────────────┘

PARÁMETROS DE CHUNKING CIENTÍFICO:
---------------------------------
Los valores 1000/200 (size/overlap) están optimizados para papers científicos:
- 1000 chars ≈ 250 tokens ≈ 1 párrafo denso de contenido
- 200 chars overlap asegura que ninguna oración quede cortada
- Separadores jerárquicos preservan estructura: \\n\\n → \\n → . → espacio

USO:
----
    from app.core.config import get_settings

    settings = get_settings()  # Singleton, siempre la misma instancia
    print(settings.embedding_model)  # "bge-m3"

VARIABLES DE ENTORNO SOPORTADAS:
-------------------------------
    OLLAMA_BASE_URL=http://localhost:11434
    EMBEDDING_MODEL=bge-m3
    LLM_MODEL=llama3.1:8b
    GROBID_URL=http://localhost:8070
    OPENALEX_EMAIL=tu@email.com
    SEMANTIC_CACHE_THRESHOLD=0.95
    (ver .env.example para lista completa)

Autor: Scientific Library RAG Team
Versión: 1.0.0
"""

from pathlib import Path
from functools import lru_cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración centralizada de la aplicación usando Pydantic Settings.

    Esta clase hereda de BaseSettings, que automáticamente:
    1. Lee variables de entorno (case-insensitive)
    2. Lee archivo .env si existe
    3. Valida tipos y rangos
    4. Proporciona valores por defecto

    PATRÓN APLICADO: Immutable Configuration
    Una vez creada la instancia, los valores no deberían cambiar durante
    la ejecución. Esto previene bugs sutiles por estado compartido mutable.

    Attributes:
        model_config: Configuración de Pydantic para carga de settings
    """

    # =========================================================================
    # CONFIGURACIÓN DE PYDANTIC SETTINGS
    # =========================================================================
    # SettingsConfigDict controla CÓMO se cargan los valores:
    # - env_file: Archivo .env a leer (desarrollo local)
    # - case_sensitive=False: OLLAMA_URL == ollama_url == Ollama_Url
    # - extra="ignore": Variables de entorno desconocidas no causan error
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # CONFIGURACIÓN DE LA APLICACIÓN
    # =========================================================================

    # Nombre descriptivo, usado en logs y documentación API
    app_name: str = "Scientific Library RAG"

    # Modo debug: activa reload automático y logging verbose
    # IMPORTANTE: Nunca True en producción (performance y seguridad)
    debug: bool = False

    # =========================================================================
    # RUTAS DEL SISTEMA DE ARCHIVOS
    # =========================================================================
    # Usamos pathlib.Path para manejo multiplataforma de rutas (Windows/Unix)
    # Path.parent sube un nivel en el árbol de directorios

    # Directorio raíz del proyecto (donde está pyproject.toml)
    base_dir: Path = Path(__file__).parent.parent.parent

    # Directorio principal de datos
    data_dir: Path = base_dir / "data"

    # Subdirectorio para PDFs originales descargados
    # Nomenclatura: {arxiv_id}.pdf o {doi_sanitizado}.pdf
    pdfs_dir: Path = data_dir / "pdfs"

    # Subdirectorio para texto extraído en formato Markdown
    # PyMuPDF4LLM genera Markdown preservando estructura (headers, tablas)
    markdown_dir: Path = data_dir / "markdown"

    # Subdirectorio para base de datos vectorial LanceDB
    # LanceDB almacena en formato columnar Lance, optimizado para SSD
    vectors_dir: Path = data_dir / "vectors"

    # Directorio para metadatos estructurados (SQLite, JSON indexes)
    metadata_dir: Path = base_dir / "metadata"

    # Directorio de caché general
    cache_dir: Path = base_dir / ".cache"

    # Subdirectorio específico para caché de embeddings
    # Organizado por modelo: .cache/embeddings/bge-m3/
    embedding_cache_dir: Path = cache_dir / "embeddings"

    # =========================================================================
    # CONFIGURACIÓN DE OLLAMA (LLM Local)
    # =========================================================================
    # Ollama es el servidor de inferencia local que ejecuta los modelos
    # Ventaja: 100% offline, sin costos de API, privacidad total

    # URL base del servidor Ollama (puerto por defecto: 11434)
    ollama_base_url: str = "http://localhost:11434"

    # -------------------------------------------------------------------------
    # MODELO DE EMBEDDINGS: BGE-M3
    # -------------------------------------------------------------------------
    # BGE-M3 (BAAI General Embedding - Multilingual, Multi-task, Multi-granularity)
    #
    # ¿POR QUÉ BGE-M3?
    # ┌──────────────────┬─────────────┬─────────────┬──────────────────────────┐
    # │ Característica   │ BGE-M3      │ Alternativas│ Beneficio                │
    # ├──────────────────┼─────────────┼─────────────┼──────────────────────────┤
    # │ Dimensiones      │ 1024        │ 768 (nomic) │ Mayor capacidad semántica│
    # │ Contexto máximo  │ 8,192 tokens│ 2,048       │ Papers completos sin     │
    # │                  │             │             │ chunking obligatorio     │
    # │ Idiomas          │ 100+        │ ~1 (inglés) │ Papers en cualquier      │
    # │                  │             │             │ idioma científico        │
    # │ MTEB Score       │ 72%         │ 57-62%      │ Mejor retrieval accuracy │
    # │ Multi-vector     │ ✓ Dense +   │ Solo dense  │ Búsqueda híbrida         │
    # │                  │   Sparse    │             │                          │
    # └──────────────────┴─────────────┴─────────────┴──────────────────────────┘
    embedding_model: str = "bge-m3"

    # Dimensionalidad de los vectores (debe coincidir con el modelo)
    # Usado para definir esquemas de LanceDB y validación
    embedding_dimensions: int = 1024

    # Fallback si BGE-M3 no está disponible (más ligero: 274MB vs 1.1GB)
    embedding_model_fallback: str = "nomic-embed-text"

    # -------------------------------------------------------------------------
    # MODELO LLM PARA GENERACIÓN
    # -------------------------------------------------------------------------
    # Llama 3.1 8B: Balance óptimo entre calidad y velocidad
    # - 8B parámetros es ejecutable en GPUs de consumo (8GB+ VRAM)
    # - Cuantización Q4 reduce a ~5GB sin pérdida significativa de calidad
    # - Soporta contexto de 128K tokens (suficiente para RAG con 10+ chunks)
    llm_model: str = "llama3.1:8b"

    # Fallback: Qwen2 7B (alternativa competitiva de Alibaba)
    llm_model_fallback: str = "qwen2:7b"

    # =========================================================================
    # CONFIGURACIÓN DE LANCEDB (Base de Datos Vectorial)
    # =========================================================================
    # LanceDB: Base de datos vectorial embedded (sin servidor separado)
    #
    # ¿POR QUÉ LANCEDB SOBRE ALTERNATIVAS?
    # ┌────────────────┬─────────────────────────────────────────────────────────┐
    # │ Característica │ Beneficio para Biblioteca Científica Offline            │
    # ├────────────────┼─────────────────────────────────────────────────────────┤
    # │ Embedded       │ No requiere proceso servidor separado - simplifica      │
    # │                │ deployment y reduce recursos                             │
    # │ Disk-native    │ Formato columnar Lance optimizado para SSD              │
    # │                │ Permite datasets mayores que RAM                         │
    # │ Escalabilidad  │ Billones de vectores (vs ~10M en ChromaDB)              │
    # │ Búsqueda       │ Híbrida: Vector + Full-text (FTS5)                      │
    # │ Índices        │ IVF-PQ para datasets grandes (1M+ papers)               │
    # └────────────────┴─────────────────────────────────────────────────────────┘

    # URI de conexión (en este caso, ruta al directorio)
    lancedb_uri: str = str(data_dir / "vectors" / "lancedb")

    # -------------------------------------------------------------------------
    # PARÁMETROS DE ÍNDICE IVF-PQ
    # -------------------------------------------------------------------------
    # IVF-PQ (Inverted File with Product Quantization) es un algoritmo de
    # indexación que permite búsquedas aproximadas muy rápidas en datasets grandes.
    #
    # CÓMO FUNCIONA IVF-PQ:
    # 1. IVF (Inverted File): Divide el espacio vectorial en `num_partitions`
    #    clusters usando K-means. En búsqueda, solo examina los clusters más
    #    cercanos al query, reduciendo dramáticamente el espacio de búsqueda.
    #
    # 2. PQ (Product Quantization): Comprime cada vector dividiéndolo en
    #    `num_sub_vectors` segmentos, cada uno cuantizado a un codebook.
    #    Reduce memoria ~4-8x con pérdida mínima de precisión.
    #
    # VALORES RECOMENDADOS (de la guía):
    # - 256 particiones: √n regla, óptimo para ~65K-1M vectores
    # - 96 sub-vectores: 1024 dims / 96 ≈ 10-11 dims por subvector (estándar)
    lancedb_num_partitions: int = 256
    lancedb_num_sub_vectors: int = 96

    # =========================================================================
    # CONFIGURACIÓN DE GROBID (Extracción de Metadatos PDF)
    # =========================================================================
    # GROBID (GeneRation Of BIbliographic Data) es una herramienta ML para
    # extraer metadatos estructurados de PDFs científicos.
    #
    # CAPACIDADES:
    # - Extrae 55+ campos en formato TEI-XML
    # - F1-score de 0.87-0.90 para referencias bibliográficas
    # - Identifica: título, autores, afiliaciones, abstract, secciones, figuras
    # - Resuelve referencias cruzadas dentro del documento
    #
    # DEPLOYMENT: Docker container (grobid/grobid:0.8.2-full)
    grobid_url: str = "http://localhost:8070"
    grobid_timeout: int = 60  # Segundos. Papers largos pueden tomar ~30s

    # =========================================================================
    # CONFIGURACIÓN DE CHUNKING (División de Texto)
    # =========================================================================
    # El chunking es CRÍTICO para la calidad del RAG. Chunks muy pequeños
    # pierden contexto; muy grandes diluyen la relevancia.
    #
    # ESTRATEGIA PARA TEXTOS CIENTÍFICOS:
    # ┌─────────────────────────────────────────────────────────────────────────┐
    # │  Paper científico típico                                                 │
    # │  ┌─────────────────────────────────────────────────────────────────────┐│
    # │  │ Abstract (≈500 chars) - Chunk único, alta densidad de información  ││
    # │  ├─────────────────────────────────────────────────────────────────────┤│
    # │  │ Introduction                                                        ││
    # │  │   Párrafo 1 (400 chars) ─┐                                          ││
    # │  │   Párrafo 2 (600 chars) ─┼─→ Chunk 1 (1000 chars)                   ││
    # │  │   Párrafo 3 (500 chars) ─┼─→ [200 chars overlap] + Chunk 2          ││
    # │  │   ...                    │                                          ││
    # │  └─────────────────────────────────────────────────────────────────────┘│
    # └─────────────────────────────────────────────────────────────────────────┘
    #
    # ¿POR QUÉ 1000/200?
    # - 1000 chars ≈ 250 tokens ≈ 1-2 párrafos densos
    # - 200 chars overlap (20%) evita cortar oraciones/ideas a la mitad
    # - BGE-M3 con 8K tokens permite ~32 chunks por contexto RAG
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Separadores jerárquicos para RecursiveCharacterTextSplitter
    # Orden de prioridad: intenta dividir por el primero, si no cabe, siguiente
    # 1. "\n\n" - Límites de párrafo (preferido, preserva ideas completas)
    # 2. "\n"   - Saltos de línea (separa oraciones largas)
    # 3. ". "   - Fin de oración (último recurso semántico)
    # 4. " "    - Espacios (fallback mecánico)
    chunk_separators: list[str] = ["\n\n", "\n", ". ", " "]

    # =========================================================================
    # CONFIGURACIÓN DE CACHÉ
    # =========================================================================

    # -------------------------------------------------------------------------
    # RETRIEVAL CACHE (Capa 2)
    # -------------------------------------------------------------------------
    # Almacena resultados de búsquedas vectoriales en memoria.
    # Key: hash(query + filters), Value: lista de chunks encontrados
    #
    # TTL (Time To Live): 30 minutos
    # - Suficiente para sesiones de estudio típicas
    # - Evita servir resultados obsoletos si se añaden nuevos papers
    # - Balance entre hits de caché y frescura de datos
    retrieval_cache_ttl: int = 1800  # 30 minutos en segundos

    # Máximo de queries cacheadas (LRU eviction)
    # 1000 entries × ~10KB/entry ≈ 10MB de memoria
    retrieval_cache_maxsize: int = 1000

    # -------------------------------------------------------------------------
    # SEMANTIC CACHE (Capa 3)
    # -------------------------------------------------------------------------
    # Almacena pares (query_embedding, full_response) en el vector store.
    # Cuando llega una nueva query, busca queries anteriores similares.
    # Si similitud ≥ threshold, retorna respuesta cacheada sin llamar al LLM.
    #
    # THRESHOLD 0.95:
    # - Muy alto: solo queries casi idénticas ("quantum computing" ≈ "quantum computing basics")
    # - Evita falsos positivos que servirían respuestas incorrectas
    # - Benchmarks muestran hasta 65x reducción de latencia para queries repetidas
    semantic_cache_threshold: float = 0.95
    semantic_cache_enabled: bool = True

    # =========================================================================
    # CONFIGURACIÓN DE RAG (Retrieval-Augmented Generation)
    # =========================================================================

    # Número de chunks a recuperar del vector store
    # 10 chunks × 1000 chars ≈ 10,000 chars ≈ 2,500 tokens de contexto
    rag_top_k: int = 10

    # Después de reranking (si se implementa), mantener top 5
    # Reranking usa modelo cross-encoder más preciso pero más lento
    rag_rerank_top_k: int = 5

    # Máximo de tokens para el contexto enviado al LLM
    # Llama 3.1 soporta 128K, pero más contexto = más lento y costoso
    # 4096 tokens es un buen balance para respuestas rápidas
    rag_max_context_length: int = 4096

    # =========================================================================
    # CONFIGURACIÓN DE RATE LIMITS PARA APIs EXTERNAS
    # =========================================================================
    # Cada API científica tiene límites diferentes. Respetarlos evita bans.

    # -------------------------------------------------------------------------
    # OPENALEX
    # -------------------------------------------------------------------------
    # OpenAlex: 240M+ papers, CC0 license, la mejor opción gratuita
    # - Sin email: 1 req/s (pool anónimo, compartido, lento)
    # - Con email: 10 req/s (pool "polite", dedicado, rápido)
    # IMPORTANTE: Usar email real, no spam, para evitar blacklist
    openalex_email: str = ""
    openalex_rate_limit: float = 0.1  # 100ms entre requests = 10 req/s

    # -------------------------------------------------------------------------
    # ARXIV
    # -------------------------------------------------------------------------
    # arXiv: 2.5M+ preprints, acceso directo a PDFs
    # Rate limit estricto: 1 request cada 3 segundos
    # Excederlo resulta en ban temporal (HTTP 429)
    arxiv_rate_limit: float = 3.0  # segundos entre requests

    # -------------------------------------------------------------------------
    # UNPAYWALL
    # -------------------------------------------------------------------------
    # Unpaywall: Encuentra versiones Open Access por DOI
    # Límite: 100,000 requests/día con email
    unpaywall_email: str = ""

    # -------------------------------------------------------------------------
    # SEMANTIC SCHOLAR
    # -------------------------------------------------------------------------
    # Semantic Scholar: 200M+ papers, API más estructurada
    # - Sin key: 100 requests / 5 minutos
    # - Con key: Límites más altos (aplicar en su web)
    semantic_scholar_api_key: str = ""

    # =========================================================================
    # CONFIGURACIÓN DEL SERVIDOR
    # =========================================================================

    # Host 0.0.0.0 = escucha en todas las interfaces de red
    # Necesario para acceso desde otros dispositivos o Docker
    host: str = "0.0.0.0"

    # Puerto personalizado (cambiado de 8000 por defecto)
    port: int = 3690

    # Número de workers (procesos paralelos)
    # IMPORTANTE: 1 worker para modelos ML
    # Cada worker carga su propia copia del modelo en memoria
    # 2 workers con Llama 8B = 10GB+ RAM, probablemente OOM
    workers: int = 1

    # =========================================================================
    # MÉTODOS DE INSTANCIA
    # =========================================================================

    def ensure_directories(self) -> None:
        """
        Crea todos los directorios necesarios si no existen.

        Este método implementa el patrón "Fail-Safe Initialization":
        en lugar de fallar si falta un directorio, lo crea automáticamente.

        Se llama durante el startup de la aplicación (lifespan handler)
        para garantizar que la estructura de archivos está lista antes
        de cualquier operación de I/O.

        Directorios creados:
        - data/pdfs/      → PDFs descargados
        - data/markdown/  → Texto extraído
        - data/vectors/   → LanceDB storage
        - metadata/       → SQLite, índices JSON
        - .cache/         → Caché general
        - .cache/embeddings/ → Caché de embeddings por modelo
        """
        for dir_path in [
            self.pdfs_dir,
            self.markdown_dir,
            self.vectors_dir,
            self.metadata_dir,
            self.cache_dir,
            self.embedding_cache_dir,
        ]:
            # parents=True: crea directorios intermedios si no existen
            # exist_ok=True: no lanza error si ya existe
            dir_path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# SINGLETON FACTORY FUNCTION
# =============================================================================

@lru_cache  # maxsize=None por defecto, cachea infinitas llamadas (en este caso, 1)
def get_settings() -> Settings:
    """
    Factory function que retorna la instancia singleton de Settings.

    PATRÓN: Singleton via functools.lru_cache

    ¿POR QUÉ SINGLETON PARA CONFIGURACIÓN?
    1. Consistencia: Todos los módulos ven la misma configuración
    2. Performance: Settings se parsea una sola vez, no en cada import
    3. Memoria: Una sola instancia, no N copias
    4. Thread-safety: lru_cache es thread-safe en Python 3.2+

    ¿POR QUÉ lru_cache EN VEZ DE VARIABLE GLOBAL?
    - Lazy initialization: Settings se crea en primer uso, no en import
    - Testing: Se puede hacer lru_cache.cache_clear() entre tests
    - Dependency injection: Fácil de mockear en tests

    FLUJO DE INICIALIZACIÓN:
    1. Primera llamada a get_settings()
    2. Settings() parsea .env + variables de entorno
    3. Pydantic valida todos los valores
    4. ensure_directories() crea estructura de archivos
    5. Instancia se cachea
    6. Llamadas subsecuentes retornan instancia cacheada

    Returns:
        Settings: Instancia singleton de la configuración

    Example:
        >>> settings = get_settings()
        >>> settings.embedding_model
        'bge-m3'
        >>> get_settings() is get_settings()  # Misma instancia
        True
    """
    settings = Settings()
    settings.ensure_directories()
    return settings
