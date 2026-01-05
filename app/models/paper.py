"""
================================================================================
MODELOS DE DOCUMENTOS CIENTÍFICOS - BIBLIOTECA RAG LOCAL
================================================================================

Este módulo define los modelos de datos Pydantic para representar papers científicos
y sus chunks vectorizados. Es el corazón del sistema de tipos del proyecto.

ARQUITECTURA DE DATOS
=====================

El flujo de datos sigue este patrón:

    ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
    │  APIs Externas  │ ──▶  │  PaperMetadata  │ ──▶  │     Paper       │
    │  (OpenAlex,     │      │  (metadatos     │      │  (documento     │
    │   arXiv, etc.)  │      │   normalizados) │      │   completo)     │
    └─────────────────┘      └─────────────────┘      └─────────────────┘
                                                              │
                                                              ▼
                                                      ┌─────────────────┐
                                                      │   PaperChunk    │
                                                      │  (fragmentos    │
                                                      │   vectorizados) │
                                                      └─────────────────┘
                                                              │
                                                              ▼
                                                      ┌─────────────────┐
                                                      │    LanceDB      │
                                                      │  (almacenamiento│
                                                      │   vectorial)    │
                                                      └─────────────────┘

IDENTIFICADORES CIENTÍFICOS
===========================

Los papers científicos tienen múltiples sistemas de identificación:

    ┌────────────────────────────────────────────────────────────────────┐
    │ Identificador │ Formato              │ Ejemplo                     │
    ├───────────────┼──────────────────────┼─────────────────────────────┤
    │ DOI           │ 10.prefix/suffix     │ 10.1038/nature12373         │
    │ arXiv ID      │ YYMM.NNNNN           │ 2301.00001                  │
    │ PMID          │ Numérico             │ 12345678                    │
    │ PMCID         │ PMC + numérico       │ PMC1234567                  │
    │ OpenAlex ID   │ W + numérico         │ W2741809807                 │
    │ S2 ID         │ Hash 40 chars        │ abc123def456...             │
    │ ORCID         │ 0000-0000-0000-0000  │ 0000-0002-1825-0097         │
    │ ROR ID        │ Alfanumérico         │ 03yrm5c26                   │
    └────────────────────────────────────────────────────────────────────┘

TAXONOMÍAS CIENTÍFICAS
======================

El sistema soporta múltiples sistemas de clasificación:

    - arXiv Categories: cs.AI, cs.LG, physics.hep-th, math.CO, etc.
    - OpenAlex Concepts: Machine Learning, Neural Networks, etc.
    - MeSH Terms: Medical Subject Headings (PubMed)
    - ACM CCS: Computing Classification System

¿POR QUÉ PYDANTIC?
==================

Pydantic v2 ofrece ventajas críticas para este sistema:

    1. VALIDACIÓN AUTOMÁTICA: Los datos de APIs externas son impredecibles
       - Campos faltantes, tipos incorrectos, formatos variados
       - Pydantic normaliza y valida automáticamente

    2. SERIALIZACIÓN EFICIENTE: model_dump() para LanceDB/JSON
       - Conversión automática datetime → string
       - Manejo de Optional fields

    3. DOCUMENTACIÓN IMPLÍCITA: Los modelos son autodocumentados
       - Field descriptions
       - Type hints
       - Default values

    4. RENDIMIENTO: Pydantic v2 usa Rust internamente
       - ~50x más rápido que v1 para validación
       - Crítico para procesar miles de papers

Designed for LanceDB storage with BGE-M3 embeddings (1024 dimensions).
"""

# =============================================================================
# IMPORTS
# =============================================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# MODELO: AUTHOR (INFORMACIÓN DE AUTORES)
# =============================================================================

class Author(BaseModel):
    """
    Información de un autor de paper científico.

    IDENTIFICADORES DE INVESTIGADORES
    ==================================

    ORCID (Open Researcher and Contributor ID)
    ------------------------------------------
    - Formato: 0000-0002-1825-0097 (16 dígitos en grupos de 4)
    - Propósito: Desambiguar autores con nombres similares
    - Cobertura: ~18 millones de investigadores registrados
    - Ejemplo problema: "John Smith" puede referir a miles de investigadores

    ROR (Research Organization Registry)
    ------------------------------------
    - Formato: 03yrm5c26 (9 caracteres alfanuméricos)
    - Propósito: Identificar instituciones de forma única
    - Cobertura: ~100,000 organizaciones de investigación
    - Ejemplo: MIT → https://ror.org/042nb2s44

    USO EN RAG
    ==========

    Los datos de autor son importantes para:
    - Filtrado por institución (ej: "papers de Stanford sobre IA")
    - Verificación de autoridad ("¿qué ha publicado Yann LeCun?")
    - Redes de colaboración (graph queries)

    Attributes:
        name: Nombre completo del autor (requerido)
        orcid: ORCID iD para desambiguación (16 dígitos)
        affiliation: Nombre de la institución en texto libre
        affiliation_ror: ROR ID de la institución (9 caracteres)
    """

    # -------------------------------------------------------------------------
    # CAMPOS DEL MODELO
    # -------------------------------------------------------------------------

    # Nombre completo del autor - único campo obligatorio
    # Puede venir en formatos variados: "Doe, John", "John Doe", "J. Doe"
    name: str

    # ORCID para identificación única del investigador
    # Formato estándar: 0000-0002-1825-0097
    # None si no está disponible (común en papers antiguos)
    orcid: Optional[str] = None

    # Nombre de la afiliación institucional en texto libre
    # Ej: "Massachusetts Institute of Technology"
    # Puede variar: "MIT", "M.I.T.", "Massachusetts Inst. of Tech."
    affiliation: Optional[str] = None

    # Research Organization Registry ID
    # Identificador único y estable para la institución
    # Resuelve el problema de variaciones en nombres de instituciones
    affiliation_ror: Optional[str] = None


# =============================================================================
# MODELO: PAPER METADATA (METADATOS NORMALIZADOS)
# =============================================================================

class PaperMetadata(BaseModel):
    """
    Metadatos de un paper científico normalizados desde múltiples APIs.

    PROCESO DE NORMALIZACIÓN
    ========================

    Cada API devuelve datos en formato diferente:

        OpenAlex          arXiv              Resultado normalizado
        ─────────         ─────              ─────────────────────
        publication_year  published          year: int
        authorships[]     authors[]          authors: list[Author]
        concepts[]        categories[]       concepts/arxiv_categories

    Este modelo actúa como "lingua franca" entre las APIs y el sistema.

    CAMPOS DE IDENTIFICACIÓN (MULTI-ID)
    ====================================

    Un paper puede tener múltiples identificadores porque:

        ┌──────────────────────────────────────────────────────────────┐
        │ Escenario                    │ IDs disponibles               │
        ├──────────────────────────────┼───────────────────────────────┤
        │ Paper publicado en journal   │ DOI, PMID, OpenAlex           │
        │ Preprint en arXiv            │ arXiv ID, (DOI si publicado)  │
        │ Paper biomédico              │ DOI, PMID, PMCID, OpenAlex    │
        │ Tesis doctoral               │ Solo DOI institucional        │
        └──────────────────────────────────────────────────────────────┘

    OPEN ACCESS (OA)
    ================

    El campo is_open_access indica disponibilidad legal:

        - Gold OA: Publicado en journal OA (ej: PLOS ONE)
        - Green OA: Versión en repositorio (ej: arXiv)
        - Hybrid: Paper OA en journal de suscripción
        - Bronze: Accesible pero sin licencia clara

    El pdf_url apunta a la mejor versión OA disponible.

    Attributes:
        doi: Digital Object Identifier (estándar industria)
        arxiv_id: arXiv identifier (preprints)
        pmid: PubMed ID (literatura biomédica)
        pmcid: PubMed Central ID (full text gratuito)
        openalex_id: OpenAlex Work ID
        semantic_scholar_id: Semantic Scholar Paper ID
        title: Título del paper (requerido)
        abstract: Resumen del paper
        authors: Lista de autores
        publication_date: Fecha exacta de publicación
        year: Año de publicación (para filtrado rápido)
        journal: Nombre del journal/venue
        volume/issue/pages: Información de ubicación en journal
        publisher: Editorial (Elsevier, Springer, etc.)
        arxiv_categories: Categorías arXiv (cs.AI, physics.hep-th)
        concepts: Conceptos OpenAlex
        mesh_terms: Medical Subject Headings
        acm_ccs: ACM Computing Classification
        is_open_access: Si el paper es OA
        oa_url: URL de la versión OA
        pdf_url: URL directa al PDF
        cited_by_count: Número de citas (impacto)
        references_count: Número de referencias
        source_api: API de origen
        retrieved_at: Timestamp de recuperación
    """

    # -------------------------------------------------------------------------
    # IDENTIFICADORES MÚLTIPLES
    # -------------------------------------------------------------------------
    # Un paper puede tener varios IDs según dónde se publicó/indexó

    # DOI: Digital Object Identifier - el más universal
    # Formato: 10.prefijo/sufijo (ej: 10.1038/nature12373)
    # Asignado por CrossRef, DataCite, etc.
    doi: Optional[str] = None

    # arXiv ID para preprints y papers de física/CS/math
    # Formato moderno: YYMM.NNNNN (ej: 2301.00001)
    # Formato antiguo: category/YYMMNNN (ej: hep-th/9905111)
    arxiv_id: Optional[str] = None

    # PubMed ID para literatura biomédica
    # Numérico simple (ej: 12345678)
    pmid: Optional[str] = None

    # PubMed Central ID - versiones full text gratuitas
    # Formato: PMC + número (ej: PMC1234567)
    pmcid: Optional[str] = None

    # OpenAlex Work ID
    # Formato: W + número (ej: W2741809807)
    openalex_id: Optional[str] = None

    # Semantic Scholar Paper ID
    # Hash de 40 caracteres hexadecimales
    semantic_scholar_id: Optional[str] = None

    # -------------------------------------------------------------------------
    # INFORMACIÓN BÁSICA
    # -------------------------------------------------------------------------

    # Título del paper - único campo obligatorio
    # Puede incluir caracteres especiales, LaTeX, unicode
    title: str

    # Abstract/resumen del paper
    # Típicamente 150-300 palabras
    # Muy importante para búsqueda semántica
    abstract: Optional[str] = None

    # Lista de autores con sus metadatos
    # Orden importante: primer autor, último autor tienen significado
    authors: list[Author] = Field(default_factory=list)

    # Fecha exacta de publicación
    # Puede ser None para preprints sin fecha específica
    publication_date: Optional[datetime] = None

    # Año de publicación como entero para filtrado eficiente
    # Extraído de publication_date o proporcionado directamente
    year: Optional[int] = None

    # -------------------------------------------------------------------------
    # INFORMACIÓN DE FUENTE/VENUE
    # -------------------------------------------------------------------------

    # Nombre del journal o conferencia
    # Ej: "Nature", "NeurIPS 2023", "arXiv preprint"
    journal: Optional[str] = None

    # Volumen del journal (ej: "42")
    volume: Optional[str] = None

    # Número/issue del journal (ej: "3")
    issue: Optional[str] = None

    # Páginas (ej: "123-145" o "e12345" para e-articles)
    pages: Optional[str] = None

    # Editorial (ej: "Elsevier", "Springer Nature", "IEEE")
    publisher: Optional[str] = None

    # -------------------------------------------------------------------------
    # CLASIFICACIÓN/TAXONOMÍAS
    # -------------------------------------------------------------------------

    # Categorías arXiv - sistema jerárquico
    # Formato: area.subcategory (ej: ["cs.AI", "cs.LG", "stat.ML"])
    # ~170 categorías activas en 8 áreas principales
    arxiv_categories: list[str] = Field(default_factory=list)

    # Conceptos OpenAlex - taxonomía jerárquica propia
    # ~65,000 conceptos derivados automáticamente
    # Ej: ["Machine Learning", "Neural Network", "Deep Learning"]
    concepts: list[str] = Field(default_factory=list)

    # Medical Subject Headings - vocabulario controlado biomédico
    # ~30,000 términos organizados jerárquicamente
    # Asignados manualmente por indexadores de NLM
    mesh_terms: list[str] = Field(default_factory=list)

    # ACM Computing Classification System
    # Taxonomía para ciencias de la computación
    # Ej: ["Computing methodologies~Machine learning"]
    acm_ccs: list[str] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # ACCESO ABIERTO
    # -------------------------------------------------------------------------

    # Flag booleano de acceso abierto
    # True si hay alguna versión OA disponible
    is_open_access: bool = False

    # URL de la página OA (puede ser landing page)
    oa_url: Optional[str] = None

    # URL directa al PDF (preferida para descarga)
    # Verificada por Unpaywall/OpenAlex
    pdf_url: Optional[str] = None

    # -------------------------------------------------------------------------
    # MÉTRICAS DE IMPACTO
    # -------------------------------------------------------------------------

    # Número de citas recibidas
    # Indicador de impacto (con limitaciones conocidas)
    # Actualizado periódicamente por OpenAlex/S2
    cited_by_count: Optional[int] = None

    # Número de referencias citadas por el paper
    # Útil para análisis bibliométrico
    references_count: Optional[int] = None

    # -------------------------------------------------------------------------
    # METADATOS DE PROCESAMIENTO
    # -------------------------------------------------------------------------

    # API de origen de estos metadatos
    # Valores: "openalex", "arxiv", "pubmed", "crossref", "semantic_scholar"
    # Útil para debugging y trazabilidad
    source_api: Optional[str] = None

    # Timestamp de cuando se recuperaron estos datos
    # Importante porque los metadatos cambian (citas, correcciones)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# MODELO: PAPER (DOCUMENTO COMPLETO)
# =============================================================================

class Paper(BaseModel):
    """
    Documento de paper completo para almacenamiento e indexación.

    ARQUITECTURA DE ALMACENAMIENTO
    ==============================

    Este modelo representa un paper "completo" con:

        ┌─────────────────────────────────────────────────────────────┐
        │                        Paper                                │
        ├─────────────────────────────────────────────────────────────┤
        │  id: string único (DOI preferido)                          │
        │  metadata: PaperMetadata (todos los metadatos)             │
        │  full_text: string (markdown extraído del PDF)             │
        │  abstract_embedding: float[1024] (vector BGE-M3)           │
        │  pdf_path: ruta al PDF local                               │
        │  markdown_path: ruta al markdown extraído                  │
        │  is_indexed: bool (si está en LanceDB)                     │
        └─────────────────────────────────────────────────────────────┘

    ESTRATEGIA DE ID
    ================

    El ID sigue un orden de preferencia:

        1. DOI (si existe) - más universal y estable
        2. arXiv ID - para preprints
        3. PMID - para literatura biomédica
        4. OpenAlex ID - fallback universal
        5. Hash del título - último recurso

    EMBEDDINGS DE ABSTRACT
    ======================

    El abstract_embedding es opcional porque:

        - Se genera asíncronamente después de ingestión
        - Puede fallar si Ollama no está disponible
        - Los chunks tienen sus propios embeddings

    Se usa para:
        - Búsqueda rápida por abstract (sin procesar full text)
        - Clustering de papers similares
        - Recomendaciones

    Attributes:
        id: Identificador único (DOI > arXiv > PMID > OpenAlex)
        metadata: Metadatos completos del paper
        full_text: Texto completo en markdown
        abstract_embedding: Vector BGE-M3 del abstract (1024 dims)
        pdf_path: Ruta local al archivo PDF
        markdown_path: Ruta local al markdown extraído
        is_indexed: Si los chunks están indexados en LanceDB
        indexed_at: Timestamp de indexación
        processing_error: Error si falló el procesamiento
    """

    # -------------------------------------------------------------------------
    # IDENTIFICACIÓN
    # -------------------------------------------------------------------------

    # Identificador único del paper en el sistema
    # Preferencia: DOI > arXiv ID > PMID > OpenAlex ID > hash(título)
    # Se usa como clave primaria en todas las operaciones
    id: str

    # Metadatos completos del paper
    # Modelo anidado con toda la información bibliográfica
    metadata: PaperMetadata

    # -------------------------------------------------------------------------
    # CONTENIDO
    # -------------------------------------------------------------------------

    # Texto completo extraído del PDF en formato markdown
    # Generado por PyMuPDF4LLM con preservación de estructura
    # Típicamente 5,000-50,000 caracteres
    full_text: Optional[str] = None

    # Embedding del abstract generado por BGE-M3
    # Vector de 1024 dimensiones (flotantes)
    # Usado para búsqueda rápida sin chunks
    abstract_embedding: Optional[list[float]] = None

    # -------------------------------------------------------------------------
    # ARCHIVOS LOCALES
    # -------------------------------------------------------------------------

    # Ruta al PDF descargado
    # Formato: data/pdfs/{id_normalizado}.pdf
    # El ID se normaliza: "/" → "_", espacios eliminados
    pdf_path: Optional[str] = None

    # Ruta al markdown extraído
    # Formato: data/markdown/{id_normalizado}.md
    # Preserva estructura: headings, listas, tablas
    markdown_path: Optional[str] = None

    # -------------------------------------------------------------------------
    # ESTADO DE PROCESAMIENTO
    # -------------------------------------------------------------------------

    # Flag indicando si el paper tiene chunks indexados
    # True después de chunking exitoso + inserción en LanceDB
    is_indexed: bool = False

    # Timestamp de cuando se completó la indexación
    # None si is_indexed es False
    indexed_at: Optional[datetime] = None

    # Mensaje de error si el procesamiento falló
    # Útil para debugging y reintentos
    # Ej: "GROBID timeout", "PDF corrupto", "Ollama unavailable"
    processing_error: Optional[str] = None


# =============================================================================
# MODELO: PAPER CHUNK (FRAGMENTOS VECTORIZADOS)
# =============================================================================

class PaperChunk(BaseModel):
    """
    Fragmento de texto vectorizado para almacenamiento en LanceDB.

    ESTRATEGIA DE CHUNKING
    ======================

    Los papers científicos requieren chunking especial:

        ┌─────────────────────────────────────────────────────────────┐
        │ Parámetro        │ Valor    │ Justificación                 │
        ├──────────────────┼──────────┼───────────────────────────────┤
        │ chunk_size       │ 1000     │ Balance precisión/contexto    │
        │ chunk_overlap    │ 200      │ Continuidad semántica         │
        │ separadores      │ jerárq.  │ Preservar estructura          │
        └─────────────────────────────────────────────────────────────┘

    Jerarquía de separadores (en orden de prioridad):

        1. "\\n\\n" - Párrafos (boundary más fuerte)
        2. "\\n"   - Líneas
        3. ". "    - Oraciones
        4. ", "    - Cláusulas
        5. " "     - Palabras (último recurso)

    ¿POR QUÉ 1000 CARACTERES?
    =========================

        - Demasiado pequeño (< 500): Pierde contexto
        - Demasiado grande (> 2000): Diluye relevancia
        - 1000 chars ≈ 250 tokens ≈ 1 párrafo científico

    OVERLAP DE 200 CARACTERES
    =========================

    El overlap asegura que conceptos en boundaries no se pierdan:

        Chunk N:    [................texto................]
        Chunk N+1:                               [......overlap......texto............]
                                                  ↑
                                            200 caracteres repetidos

    ESQUEMA EN LANCEDB
    ==================

    Este modelo se almacena en la tabla "paper_chunks":

        paper_id: string (FK a Paper)
        chunk_index: int32 (orden en el documento)
        text: string (contenido del chunk)
        section: string (sección del paper)
        vector: fixed_size_list<float32>[1024] (embedding BGE-M3)
        year: int32 (para filtrado)
        arxiv_categories: list<string> (para filtrado)

    Attributes:
        paper_id: ID del paper padre (FK)
        chunk_index: Índice del chunk (0-based)
        text: Contenido textual del chunk
        section: Sección del paper (abstract, methods, etc.)
        vector: Embedding BGE-M3 de 1024 dimensiones
        year: Año para filtrado rápido
        arxiv_categories: Categorías para filtrado
    """

    # -------------------------------------------------------------------------
    # REFERENCIA AL PAPER PADRE
    # -------------------------------------------------------------------------

    # ID del paper al que pertenece este chunk
    # Usado para JOINs y reconstrucción del contexto
    paper_id: str

    # Índice del chunk dentro del paper (0-based)
    # Permite ordenar chunks para mostrar contexto
    chunk_index: int

    # -------------------------------------------------------------------------
    # CONTENIDO
    # -------------------------------------------------------------------------

    # Texto del chunk (≤1000 caracteres típicamente)
    # Puede ser menor si el separador natural está antes
    text: str

    # Sección del paper donde está el chunk
    # Valores típicos: "abstract", "introduction", "methods",
    # "results", "discussion", "conclusion", "references"
    # Detectado por patrones en el texto
    section: Optional[str] = None

    # -------------------------------------------------------------------------
    # VECTOR EMBEDDING
    # -------------------------------------------------------------------------

    # Vector embedding generado por BGE-M3
    # Dimensiones: 1024 (fijo)
    # Normalizado a L2 para similitud coseno
    # Tipo: list[float] pero en LanceDB es FixedSizeList<Float32>
    vector: list[float] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # METADATOS PARA FILTRADO
    # -------------------------------------------------------------------------

    # Año del paper (denormalizado para filtrado eficiente)
    # Evita JOINs costosos en queries
    year: Optional[int] = None

    # Categorías arXiv (denormalizadas)
    # Permite filtros como: "chunks de cs.AI publicados en 2023"
    arxiv_categories: list[str] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # CONFIGURACIÓN PYDANTIC
    # -------------------------------------------------------------------------

    class Config:
        """
        Configuración Pydantic para compatibilidad con LanceDB.

        arbitrary_types_allowed = True es necesario porque:
        - LanceDB usa PyArrow arrays internamente
        - Los vectors pueden ser numpy arrays en memoria
        - Pydantic por defecto solo acepta tipos Python estándar
        """
        arbitrary_types_allowed = True


# =============================================================================
# MODELO: SEARCH QUERY (PARÁMETROS DE BÚSQUEDA)
# =============================================================================

class SearchQuery(BaseModel):
    """
    Parámetros de búsqueda vectorial/híbrida.

    TIPOS DE BÚSQUEDA
    =================

        ┌──────────────────────────────────────────────────────────────┐
        │ Tipo          │ Descripción           │ Uso                  │
        ├───────────────┼───────────────────────┼──────────────────────┤
        │ Vector        │ Similitud semántica   │ "papers sobre X"     │
        │ Full-text     │ Coincidencia exacta   │ "contiene término Y" │
        │ Híbrida       │ Combinación ponderada │ Lo mejor de ambos    │
        └──────────────────────────────────────────────────────────────┘

    BÚSQUEDA HÍBRIDA (RRF)
    ======================

    Cuando hybrid=True, se usa Reciprocal Rank Fusion:

        score_final = Σ (1 / (k + rank_i))

    Donde k=60 es constante de suavizado y rank_i es la posición
    en cada lista de resultados (vector, full-text).

    FILTROS
    =======

    Los filtros se aplican ANTES de la búsqueda vectorial:

        1. year_min/year_max: Rango temporal
        2. categories: Lista de categorías arXiv (OR)
        3. authors: Lista de nombres de autor (OR)

    Esto es más eficiente que filtrar post-búsqueda.

    Attributes:
        query: Texto de búsqueda
        top_k: Número de resultados (1-100)
        year_min: Año mínimo (inclusive)
        year_max: Año máximo (inclusive)
        categories: Categorías arXiv para filtrar
        authors: Nombres de autores para filtrar
        hybrid: Si usar búsqueda híbrida
    """

    # -------------------------------------------------------------------------
    # QUERY
    # -------------------------------------------------------------------------

    # Texto de búsqueda del usuario
    # Se vectoriza con BGE-M3 para búsqueda semántica
    query: str

    # Número de resultados a retornar
    # Rango: 1-100 (limitado para rendimiento)
    # Default: 10 (balance precisión/recall)
    top_k: int = Field(default=10, ge=1, le=100)

    # -------------------------------------------------------------------------
    # FILTROS TEMPORALES
    # -------------------------------------------------------------------------

    # Año mínimo de publicación (inclusive)
    # Ej: year_min=2020 excluye papers pre-2020
    year_min: Optional[int] = None

    # Año máximo de publicación (inclusive)
    # Ej: year_max=2023 excluye papers post-2023
    year_max: Optional[int] = None

    # -------------------------------------------------------------------------
    # FILTROS CATEGÓRICOS
    # -------------------------------------------------------------------------

    # Lista de categorías arXiv
    # Operador: OR (cualquier categoría coincide)
    # Ej: ["cs.AI", "cs.LG"] → papers de IA o ML
    categories: list[str] = Field(default_factory=list)

    # Lista de nombres de autores
    # Operador: OR (cualquier autor coincide)
    # Búsqueda parcial: "LeCun" matchea "Yann LeCun"
    authors: list[str] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # MODO DE BÚSQUEDA
    # -------------------------------------------------------------------------

    # Flag para búsqueda híbrida (vector + full-text)
    # True: Combina resultados con RRF
    # False: Solo búsqueda vectorial
    hybrid: bool = True


# =============================================================================
# MODELO: SEARCH RESULT (RESULTADO DE BÚSQUEDA)
# =============================================================================

class SearchResult(BaseModel):
    """
    Resultado individual de búsqueda vectorial.

    SCORING
    =======

    El score varía según el tipo de búsqueda:

        - Vector puro: Similitud coseno [0, 1]
        - Full-text: BM25 score [0, ∞)
        - Híbrido: RRF score [0, 1]

    SNIPPETS
    ========

    El campo snippet contiene texto resaltado:

        "...propusieron un modelo de <mark>atención</mark>
         que revolucionó el campo del <mark>NLP</mark>..."

    El resaltado se genera con regex sobre términos del query.

    Attributes:
        paper_id: ID del paper
        chunk_index: Índice del chunk (None si búsqueda por abstract)
        text: Texto del chunk/abstract
        score: Puntuación de relevancia
        metadata: Metadatos del paper
        snippet: Texto con términos resaltados
    """

    # -------------------------------------------------------------------------
    # IDENTIFICACIÓN
    # -------------------------------------------------------------------------

    # ID del paper que contiene este resultado
    paper_id: str

    # Índice del chunk dentro del paper
    # None si el resultado es del abstract (no chunk)
    chunk_index: Optional[int] = None

    # -------------------------------------------------------------------------
    # CONTENIDO
    # -------------------------------------------------------------------------

    # Texto del chunk o abstract
    # Completo, sin truncar
    text: str

    # Score de relevancia
    # Interpretación depende del tipo de búsqueda
    score: float

    # Metadatos del paper para contexto
    # Permite mostrar título, autores, año sin JOIN
    metadata: PaperMetadata

    # -------------------------------------------------------------------------
    # PRESENTACIÓN
    # -------------------------------------------------------------------------

    # Fragmento de texto con términos resaltados
    # Útil para mostrar contexto en UI
    # Formato: términos en <mark>...</mark>
    snippet: Optional[str] = None
