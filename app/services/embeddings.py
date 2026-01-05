"""
================================================================================
SERVICIO DE EMBEDDINGS - VECTORIZACIÓN DE TEXTO CIENTÍFICO
================================================================================

Este módulo implementa el servicio de embeddings usando BGE-M3 vía Ollama,
con caché persistente en disco para evitar re-computaciones costosas.

¿QUÉ SON LOS EMBEDDINGS?
========================

Los embeddings son representaciones numéricas de texto en un espacio vectorial
de alta dimensión donde la distancia semántica se traduce a distancia geométrica:

    ┌────────────────────────────────────────────────────────────────────────┐
    │                    ESPACIO DE EMBEDDINGS                               │
    │                                                                        │
    │    "machine learning"  ─────●                                         │
    │                              \                                         │
    │                               \  distancia pequeña = semántica similar │
    │                                ●───── "deep learning"                  │
    │                                                                        │
    │                                                                        │
    │    "receta de cocina" ───────────────────────────────●                │
    │                           distancia grande = semántica diferente       │
    └────────────────────────────────────────────────────────────────────────┘

¿POR QUÉ BGE-M3?
================

BGE-M3 (BAAI General Embedding M3) es el modelo elegido por sus características:

    ┌────────────────────────────────────────────────────────────────────┐
    │ Característica     │ BGE-M3         │ Alternativas              │
    ├────────────────────┼────────────────┼───────────────────────────┤
    │ Dimensiones        │ 1024           │ 768 (BERT), 1536 (OpenAI) │
    │ Contexto máximo    │ 8192 tokens    │ 512 (típico)              │
    │ Idiomas            │ 100+           │ 1-30 (típico)             │
    │ MTEB Score         │ 72%            │ 68-75% (competidores)     │
    │ Licencia           │ MIT            │ Varia                     │
    │ Ejecución local    │ ✓ (Ollama)     │ A veces                   │
    └────────────────────────────────────────────────────────────────────┘

    Para papers científicos, el contexto de 8192 tokens es crucial:
    - Abstracts largos pueden llegar a 500+ tokens
    - Chunks de 1000 caracteres ≈ 250 tokens
    - BGE-M3 puede procesar múltiples chunks en contexto

ARQUITECTURA DE CACHÉ
=====================

El sistema implementa "CacheBackedEmbeddings", un patrón de LangChain:

    ┌────────────────────────────────────────────────────────────────────────┐
    │                       FLUJO DE EMBEDDING                               │
    │                                                                        │
    │   Texto entrada: "The transformer architecture uses..."               │
    │                          │                                             │
    │                          ▼                                             │
    │              ┌───────────────────────┐                                 │
    │              │  SHA256(texto) = key  │                                 │
    │              │  "a7f3c9..."          │                                 │
    │              └───────────────────────┘                                 │
    │                          │                                             │
    │                          ▼                                             │
    │              ┌───────────────────────┐                                 │
    │              │   Buscar en caché     │                                 │
    │              │   (diskcache)         │                                 │
    │              └───────────────────────┘                                 │
    │                    │           │                                       │
    │               HIT  │           │ MISS                                  │
    │                    ▼           ▼                                       │
    │   ┌─────────────────────┐  ┌─────────────────────┐                    │
    │   │ Retornar vector     │  │ Llamar Ollama API   │                    │
    │   │ desde disco (~1ms)  │  │ + guardar en caché  │                    │
    │   │                     │  │ (~200-500ms)        │                    │
    │   └─────────────────────┘  └─────────────────────┘                    │
    └────────────────────────────────────────────────────────────────────────┘

¿POR QUÉ DISKCACHE?
===================

diskcache ofrece ventajas sobre alternativas:

    ┌────────────────────────────────────────────────────────────────────┐
    │ Librería      │ Persistencia │ Tamaño máx  │ Concurrencia         │
    ├───────────────┼──────────────┼─────────────┼──────────────────────┤
    │ diskcache     │ SQLite       │ ~TB         │ ✓ (multi-proceso)    │
    │ shelve        │ DBM          │ ~GB         │ ✗                    │
    │ lru_cache     │ Memoria      │ ~MB         │ ✗ (thread-safe)      │
    │ redis         │ Externo      │ ~TB         │ ✓ (requiere server)  │
    └────────────────────────────────────────────────────────────────────┘

    diskcache es ideal para embeddings porque:
    - Los vectores de 1024 floats ocupan ~4KB cada uno
    - 1M de embeddings ≈ 4GB (cabe fácilmente)
    - Acceso rápido via SQLite optimizado

FALLBACK MODEL
==============

Si BGE-M3 no está disponible, el sistema intenta usar nomic-embed-text:

    ┌────────────────────────────────────────────────────────────────────┐
    │ Modelo            │ Dims │ Contexto │ Tamaño │ Uso                 │
    ├───────────────────┼──────┼──────────┼────────┼─────────────────────┤
    │ bge-m3 (primario) │ 1024 │ 8192     │ 2.2GB  │ GPU recomendada     │
    │ nomic-embed-text  │ 768  │ 8192     │ 274MB  │ CPU-friendly        │
    └────────────────────────────────────────────────────────────────────┘

    Nota: Cambiar de modelo invalida el caché (diferentes dimensiones).

Features:
- BGE-M3: 1024 dims, 8192 context, 100+ languages, 72% MTEB
- CacheBackedEmbeddings: Persists to disk, avoids re-processing
- Batch processing for efficiency
- Fallback to nomic-embed-text if BGE-M3 unavailable
"""

# =============================================================================
# IMPORTS
# =============================================================================

import hashlib          # Para generar claves de caché únicas
import json             # Para serialización (no usado actualmente, pero disponible)
from functools import lru_cache  # Para singleton del servicio
from pathlib import Path
from typing import Optional

import ollama           # Cliente oficial de Ollama
from diskcache import Cache  # Caché persistente en disco (SQLite)
from tenacity import retry, stop_after_attempt, wait_exponential  # Retry con backoff

from app.core.config import get_settings


# =============================================================================
# CLASE: EMBEDDING SERVICE
# =============================================================================

class EmbeddingService:
    """
    Servicio de embeddings usando Ollama con caché persistente en disco.

    PATRÓN CACHEBACKEDEMBEDDINGS
    ============================

    Este patrón, popularizado por LangChain, envuelve un modelo de embeddings
    con una capa de caché que:

        1. Hashea el texto de entrada para generar una clave única
        2. Busca el embedding en caché antes de computar
        3. Si hay hit, retorna inmediatamente
        4. Si hay miss, genera embedding y lo almacena

    BENEFICIOS
    ==========

        - Evita re-computar embeddings para textos ya procesados
        - Crítico para RAG donde el mismo chunk se busca múltiples veces
        - Persiste entre reinicios del servidor
        - Reduce latencia: ~1ms (caché) vs ~200-500ms (modelo)

    ESTRUCTURA DEL CACHÉ
    ====================

        .cache/
        └── embeddings/
            └── bge-m3/
                ├── cache.db          # SQLite con key-value
                ├── cache.db-shm      # Shared memory (write-ahead log)
                └── cache.db-wal      # Write-ahead log

    USO TÍPICO
    ==========

        >>> service = EmbeddingService()
        >>> vec = service.embed_text("What is machine learning?")
        >>> len(vec)  # 1024 dimensiones
        1024
        >>> # Segunda llamada usa caché
        >>> vec2 = service.embed_text("What is machine learning?")

    Implements CacheBackedEmbeddings pattern from LangChain for
    persistent embedding cache, avoiding re-computation.
    """

    # -------------------------------------------------------------------------
    # INICIALIZACIÓN
    # -------------------------------------------------------------------------

    def __init__(
        self,
        model: str = "bge-m3",
        cache_dir: Optional[Path] = None,
        ollama_host: Optional[str] = None,
    ):
        """
        Inicializa el servicio de embeddings.

        PARÁMETROS
        ==========

        model: Modelo de embedding a usar
        --------------------------------
            Default: "bge-m3"
            Alternativas: "nomic-embed-text", "all-minilm"

            El modelo debe estar instalado en Ollama:
                $ ollama pull bge-m3

        cache_dir: Directorio para almacenar el caché
        ---------------------------------------------
            Default: Usa settings.embedding_cache_dir (.cache/embeddings)
            Cada modelo tiene su subdirectorio para evitar colisiones

        ollama_host: URL del servidor Ollama
        ------------------------------------
            Default: Usa settings.ollama_base_url (http://localhost:11434)
            En Docker: "http://ollama:11434" (nombre del servicio)

        Args:
            model: Embedding model name (default: bge-m3)
            cache_dir: Directory for embedding cache
            ollama_host: Ollama server URL
        """
        # Obtener configuración global
        settings = get_settings()

        # Configuración del modelo
        # model: Modelo principal a usar (bge-m3 por defecto)
        self.model = model

        # fallback_model: Modelo alternativo si el principal no está disponible
        # Configurado en settings como nomic-embed-text (más ligero)
        self.fallback_model = settings.embedding_model_fallback

        # dimensions: Número de dimensiones del vector de salida
        # BGE-M3 usa 1024, nomic-embed-text usa 768
        self.dimensions = settings.embedding_dimensions

        # ---------------------------------------------------------------------
        # CLIENTE OLLAMA
        # ---------------------------------------------------------------------

        # URL del servidor Ollama
        # En desarrollo local: http://localhost:11434
        # En Docker: http://ollama:11434
        self.ollama_host = ollama_host or settings.ollama_base_url

        # Cliente oficial de Ollama
        # Soporta: generate, chat, embed, list, pull, etc.
        self._client = ollama.Client(host=self.ollama_host)

        # ---------------------------------------------------------------------
        # CACHÉ EN DISCO
        # ---------------------------------------------------------------------

        # Directorio base del caché
        # Se crea un subdirectorio por modelo: .cache/embeddings/bge-m3/
        cache_path = cache_dir or settings.embedding_cache_dir
        cache_path.mkdir(parents=True, exist_ok=True)

        # diskcache.Cache: Almacenamiento key-value persistente
        # Usa SQLite internamente, soporta acceso concurrente
        # Cada modelo tiene su propio caché para evitar colisiones
        self._cache = Cache(str(cache_path / self.model))

        # ---------------------------------------------------------------------
        # ESTADO
        # ---------------------------------------------------------------------

        # Flag para rastrear disponibilidad del modelo
        # None = no verificado, True = disponible, False = no disponible
        # Se verifica lazy al primer uso
        self._model_available: Optional[bool] = None

    # -------------------------------------------------------------------------
    # MÉTODOS PRIVADOS: CACHÉ Y VERIFICACIÓN
    # -------------------------------------------------------------------------

    def _cache_key(self, text: str) -> str:
        """
        Genera una clave de caché única a partir del texto.

        ALGORITMO
        =========

        Usa SHA256 para generar un hash determinístico:

            texto → bytes (UTF-8) → SHA256 → hex string (64 chars)

        PROPIEDADES DEL HASH
        ====================

            - Determinístico: mismo texto = misma clave siempre
            - Único: colisiones son prácticamente imposibles (2^256)
            - Fijo: siempre 64 caracteres, independiente del largo del texto
            - Rápido: SHA256 es muy eficiente

        EJEMPLO
        =======

            >>> _cache_key("Hello world")
            "64ec88ca00b268e5ba1a35678a1b5316d212f4f366b2477232534a8aeca37f3c"

        Args:
            text: Texto a hashear

        Returns:
            str: Hash SHA256 en hexadecimal (64 caracteres)
        """
        # Codificar texto a bytes UTF-8 y hashear
        return hashlib.sha256(text.encode()).hexdigest()

    def _check_model_available(self) -> bool:
        """
        Verifica si el modelo de embeddings está disponible en Ollama.

        LÓGICA
        ======

        1. Si ya verificamos, retornar resultado cacheado
        2. Listar modelos disponibles en Ollama
        3. Buscar el modelo principal
        4. Si no está, intentar con el fallback
        5. Cachear resultado para evitar re-verificación

        FALLBACK AUTOMÁTICO
        ===================

        Si bge-m3 no está disponible pero nomic-embed-text sí,
        el servicio cambia automáticamente al modelo fallback.

        Esto permite que el sistema funcione incluso si el usuario
        olvidó descargar el modelo principal.

        Returns:
            bool: True si hay un modelo disponible
        """
        # Cache del resultado para evitar llamadas repetidas
        if self._model_available is not None:
            return self._model_available

        try:
            # Listar modelos instalados en Ollama
            # Formato: {"models": [{"name": "bge-m3:latest", ...}, ...]}
            models = self._client.list()

            # Extraer solo el nombre base (sin :latest)
            available = [m["name"].split(":")[0] for m in models.get("models", [])]

            # Verificar si el modelo principal está disponible
            self._model_available = self.model in available

            if not self._model_available:
                # Intentar con el modelo fallback
                if self.fallback_model in available:
                    # Cambiar al modelo fallback automáticamente
                    self.model = self.fallback_model
                    self._model_available = True
                    # Nota: Esto significa que el caché se almacenará
                    # en el directorio del fallback model

        except Exception:
            # Si hay error de conexión con Ollama, marcar como no disponible
            self._model_available = False

        return self._model_available

    # -------------------------------------------------------------------------
    # MÉTODO PRIVADO: LLAMADA A OLLAMA
    # -------------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _embed_with_ollama(self, texts: list[str]) -> list[list[float]]:
        """
        Genera embeddings usando el API de Ollama.

        DECORADOR @retry
        ================

        Usa tenacity para retry automático con exponential backoff:

            - stop_after_attempt(3): Máximo 3 intentos
            - wait_exponential: Espera 1s, 2s, 4s... entre intentos
            - multiplier=1, min=1, max=10: Parámetros del backoff

        Esto maneja errores transitorios como:
            - Ollama ocupado procesando otra petición
            - Timeout temporal de red
            - GPU temporalmente ocupada

        API DE OLLAMA
        =============

        El endpoint /api/embed de Ollama:

            POST /api/embed
            {
                "model": "bge-m3",
                "input": ["text1", "text2", ...]
            }

            Response:
            {
                "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]]
            }

        BATCHING
        ========

        Ollama procesa múltiples textos en una sola llamada:
            - Más eficiente que llamadas individuales
            - Mejor utilización de GPU
            - Reduce overhead de red

        Args:
            texts: Lista de textos a vectorizar

        Returns:
            Lista de vectores de embeddings (1024 dims cada uno para BGE-M3)
        """
        # Llamar al endpoint embed de Ollama
        # input puede ser un string o lista de strings
        response = self._client.embed(model=self.model, input=texts)

        # Extraer la lista de embeddings de la respuesta
        return response["embeddings"]

    # -------------------------------------------------------------------------
    # MÉTODOS PÚBLICOS: EMBEDDING DE TEXTO
    # -------------------------------------------------------------------------

    def embed_text(self, text: str) -> list[float]:
        """
        Genera embedding para un texto individual con caché.

        FLUJO
        =====

            1. Generar clave de caché: SHA256(texto)
            2. Buscar en caché
            3. Si hit: retornar vector cacheado
            4. Si miss: generar con Ollama y cachear

        USO
        ===

            >>> service = get_embedding_service()
            >>> vec = service.embed_text("What is attention?")
            >>> len(vec)
            1024
            >>> type(vec)
            <class 'list'>  # lista de floats

        RENDIMIENTO
        ===========

            - Con caché: ~1ms
            - Sin caché: ~200-500ms (depende de GPU/CPU)

        Args:
            text: Texto a vectorizar

        Returns:
            Vector de embedding (1024 floats para BGE-M3)

        Raises:
            RuntimeError: Si el modelo no está disponible
        """
        # Paso 1: Generar clave de caché
        cache_key = self._cache_key(text)

        # Paso 2: Buscar en caché
        cached = self._cache.get(cache_key)
        if cached is not None:
            # Cache hit - retornar inmediatamente
            return cached

        # Paso 3: Verificar disponibilidad del modelo
        if not self._check_model_available():
            raise RuntimeError(
                f"Embedding model {self.model} not available. "
                f"Run: ollama pull {self.model}"
            )

        # Paso 4: Generar embedding con Ollama
        embeddings = self._embed_with_ollama([text])
        embedding = embeddings[0]

        # Paso 5: Cachear resultado para uso futuro
        self._cache.set(cache_key, embedding)

        return embedding

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = True,
    ) -> list[list[float]]:
        """
        Genera embeddings para múltiples textos con caché y batching.

        OPTIMIZACIÓN POR BATCHING
        =========================

        Procesar textos en lotes es más eficiente:

            Individual (N llamadas):
                embed("text1") → 200ms
                embed("text2") → 200ms
                embed("text3") → 200ms
                Total: 600ms

            Batch (1 llamada):
                embed(["text1", "text2", "text3"]) → 250ms
                Total: 250ms (2.4x más rápido)

        ALGORITMO
        =========

            1. Separar textos cacheados de no cacheados
            2. Para textos no cacheados:
               a. Dividir en batches de 32
               b. Procesar cada batch con Ollama
               c. Cachear resultados
            3. Ensamblar resultados en orden original

        PROGRESO
        ========

        Si show_progress=True, muestra barra de progreso con tqdm:

            Embedding (bge-m3): 100%|███████| 10/10 [00:02<00:00, 3.5it/s]

        Args:
            texts: Lista de textos a vectorizar
            batch_size: Textos por batch (default 32, óptimo para GPU)
            show_progress: Mostrar barra de progreso

        Returns:
            Lista de vectores de embedding, en el mismo orden que texts

        Raises:
            RuntimeError: Si el modelo no está disponible
        """
        # Verificar disponibilidad del modelo antes de procesar
        if not self._check_model_available():
            raise RuntimeError(
                f"Embedding model {self.model} not available. "
                f"Run: ollama pull {self.model}"
            )

        # ---------------------------------------------------------------------
        # FASE 1: SEPARAR CACHEADOS DE NO CACHEADOS
        # ---------------------------------------------------------------------

        results: list[list[float]] = []     # Resultados finales
        uncached_indices: list[int] = []    # Índices de textos no cacheados
        uncached_texts: list[str] = []      # Textos no cacheados

        # Verificar caché para cada texto
        for i, text in enumerate(texts):
            cache_key = self._cache_key(text)
            cached = self._cache.get(cache_key)

            if cached is not None:
                # Cache hit - agregar resultado directamente
                results.append(cached)
            else:
                # Cache miss - agregar placeholder y marcar para procesar
                results.append([])  # Placeholder vacío
                uncached_indices.append(i)
                uncached_texts.append(text)

        # ---------------------------------------------------------------------
        # FASE 2: PROCESAR TEXTOS NO CACHEADOS EN BATCHES
        # ---------------------------------------------------------------------

        if uncached_texts:
            # Configurar iterador con o sin barra de progreso
            if show_progress:
                from tqdm import tqdm

                # tqdm muestra: Embedding (bge-m3): 75%|████ | 3/4
                iterator = tqdm(
                    range(0, len(uncached_texts), batch_size),
                    desc=f"Embedding ({self.model})",
                )
            else:
                iterator = range(0, len(uncached_texts), batch_size)

            # Procesar cada batch
            for batch_start in iterator:
                batch_end = min(batch_start + batch_size, len(uncached_texts))
                batch = uncached_texts[batch_start:batch_end]

                # Generar embeddings para el batch completo
                batch_embeddings = self._embed_with_ollama(batch)

                # Almacenar resultados en las posiciones correctas
                for j, embedding in enumerate(batch_embeddings):
                    # Calcular índice original en la lista de entrada
                    idx = uncached_indices[batch_start + j]
                    results[idx] = embedding

                    # Cachear para uso futuro
                    cache_key = self._cache_key(batch[j])
                    self._cache.set(cache_key, embedding)

        return results

    # -------------------------------------------------------------------------
    # MÉTODOS PÚBLICOS: UTILIDADES
    # -------------------------------------------------------------------------

    def similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """
        Calcula la similitud coseno entre dos embeddings.

        SIMILITUD COSENO
        ================

        La similitud coseno mide el ángulo entre dos vectores:

                         A · B
            cos(θ) = ─────────────
                      ||A|| ||B||

        Donde:
            - A · B = producto punto (suma de productos elemento a elemento)
            - ||A|| = norma L2 (sqrt de suma de cuadrados)

        INTERPRETACIÓN
        ==============

            ┌────────────────────────────────────────────────────────────┐
            │ Score    │ Interpretación                                 │
            ├──────────┼────────────────────────────────────────────────┤
            │ 0.95-1.0 │ Casi idéntico (mismo concepto)                │
            │ 0.80-0.95│ Muy similar (mismo tema)                       │
            │ 0.60-0.80│ Relacionado (tema adyacente)                   │
            │ 0.40-0.60│ Vagamente relacionado                          │
            │ 0.00-0.40│ No relacionado                                 │
            └────────────────────────────────────────────────────────────┘

        USO
        ===

            >>> vec1 = service.embed_text("machine learning")
            >>> vec2 = service.embed_text("deep learning")
            >>> service.similarity(vec1, vec2)
            0.92  # Muy similar

            >>> vec3 = service.embed_text("cooking recipe")
            >>> service.similarity(vec1, vec3)
            0.15  # No relacionado

        Args:
            embedding1: Primer vector de embedding
            embedding2: Segundo vector de embedding

        Returns:
            Score de similitud coseno [0, 1]
        """
        import numpy as np

        # Convertir listas a arrays numpy para operaciones vectoriales
        v1 = np.array(embedding1)
        v2 = np.array(embedding2)

        # Calcular producto punto
        dot_product = np.dot(v1, v2)

        # Calcular normas L2
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        # Evitar división por cero
        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calcular y retornar similitud coseno
        return float(dot_product / (norm1 * norm2))

    def get_cache_stats(self) -> dict:
        """
        Obtiene estadísticas del caché de embeddings.

        MÉTRICAS RETORNADAS
        ===================

            - model: Nombre del modelo actual
            - cache_size: Número de embeddings cacheados
            - cache_path: Ruta al directorio del caché

        EJEMPLO
        =======

            >>> service.get_cache_stats()
            {
                "model": "bge-m3",
                "cache_size": 1523,
                "cache_path": "/app/.cache/embeddings/bge-m3"
            }

        USO TÍPICO
        ==========

            - Monitoreo del uso de caché
            - Debugging de problemas de espacio
            - Estadísticas en dashboard

        Returns:
            Diccionario con estadísticas del caché
        """
        return {
            "model": self.model,
            "cache_size": len(self._cache),  # Número de entradas
            "cache_path": str(self._cache.directory),
        }

    def clear_cache(self) -> None:
        """
        Limpia completamente el caché de embeddings.

        CUÁNDO USAR
        ===========

            - Al cambiar de modelo de embeddings
            - Al actualizar a nueva versión del modelo
            - Para liberar espacio en disco
            - Durante testing/debugging

        ADVERTENCIA
        ===========

            ¡Esto borra TODOS los embeddings cacheados!
            La próxima vez que se soliciten, se re-computarán.

            Para un corpus de 10,000 chunks, esto puede significar
            ~30-60 minutos de re-procesamiento.

        EJEMPLO
        =======

            >>> service.get_cache_stats()["cache_size"]
            1523
            >>> service.clear_cache()
            >>> service.get_cache_stats()["cache_size"]
            0
        """
        self._cache.clear()


# =============================================================================
# SINGLETON: GET EMBEDDING SERVICE
# =============================================================================

@lru_cache
def get_embedding_service() -> EmbeddingService:
    """
    Obtiene una instancia singleton del servicio de embeddings.

    PATRÓN SINGLETON VIA LRU_CACHE
    ==============================

    @lru_cache sin argumentos crea un singleton:

        - Primera llamada: Crea la instancia
        - Llamadas subsecuentes: Retorna la misma instancia

    ¿POR QUÉ SINGLETON?
    ===================

        1. CONEXIÓN PERSISTENTE: Mantiene conexión con Ollama
        2. CACHÉ COMPARTIDO: Todos usan el mismo caché de disco
        3. EFICIENCIA: Evita re-inicialización costosa
        4. CONSISTENCIA: Mismo estado en toda la aplicación

    USO
    ===

        # En cualquier parte del código:
        service = get_embedding_service()
        vec = service.embed_text("Hello world")

        # En otro módulo, misma instancia:
        service2 = get_embedding_service()
        assert service is service2  # True

    CONFIGURACIÓN
    =============

    La instancia se configura desde get_settings():
        - embedding_model: Modelo a usar (bge-m3)
        - embedding_cache_dir: Directorio del caché
        - ollama_base_url: URL de Ollama

    Returns:
        Instancia singleton de EmbeddingService
    """
    settings = get_settings()
    return EmbeddingService(
        model=settings.embedding_model,
        cache_dir=settings.embedding_cache_dir,
        ollama_host=settings.ollama_base_url,
    )
