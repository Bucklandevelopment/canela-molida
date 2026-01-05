"""
================================================================================
MODELOS DE RESPUESTAS DE APIs EXTERNAS - BIBLIOTECA CIENTÍFICA
================================================================================

Este módulo define los modelos Pydantic para normalizar las respuestas de las
APIs científicas externas que alimentan el sistema.

ECOSISTEMA DE APIs CIENTÍFICAS
==============================

El sistema integra múltiples fuentes de datos académicos:

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                    FUENTES DE DATOS CIENTÍFICOS                         │
    │                                                                         │
    │   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐            │
    │   │   OpenAlex    │   │    arXiv      │   │   Unpaywall   │            │
    │   │   240M+ docs  │   │   2.5M+ docs  │   │   OA lookup   │            │
    │   │   CC0         │   │   No auth     │   │   100K/day    │            │
    │   └───────┬───────┘   └───────┬───────┘   └───────┬───────┘            │
    │           │                   │                   │                     │
    │           ▼                   ▼                   ▼                     │
    │   ┌─────────────────────────────────────────────────────────────┐      │
    │   │                 MODELOS DE NORMALIZACIÓN                    │      │
    │   │  OpenAlexWork → PaperMetadata                               │      │
    │   │  ArxivEntry → PaperMetadata                                 │      │
    │   │  UnpaywallResponse → pdf_url, is_oa                         │      │
    │   └─────────────────────────────────────────────────────────────┘      │
    │                                                                         │
    │   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐            │
    │   │ Semantic S2   │   │  Nobel API    │   │   Wikidata    │            │
    │   │   200M+ docs  │   │   Since 1901  │   │   SPARQL      │            │
    │   │   100/5min    │   │   No auth     │   │   No limit    │            │
    │   └───────────────┘   └───────────────┘   └───────────────┘            │
    └─────────────────────────────────────────────────────────────────────────┘

¿POR QUÉ MODELOS SEPARADOS POR API?
====================================

Cada API tiene su propio esquema de datos:

    ┌────────────────────────────────────────────────────────────────────┐
    │ Campo         │ OpenAlex          │ arXiv          │ S2            │
    ├───────────────┼───────────────────┼────────────────┼───────────────┤
    │ Año           │ publication_year  │ published      │ year          │
    │ Abstract      │ abstract_inv_idx  │ summary        │ abstract      │
    │ Autores       │ authorships[]     │ authors[]      │ authors[]     │
    │ OA            │ open_access{}     │ (siempre OA)   │ isOpenAccess  │
    │ Categorías    │ concepts[]        │ categories[]   │ fieldsOfStudy │
    └────────────────────────────────────────────────────────────────────┘

Los modelos específicos por API:
    1. Preservan la estructura original (debugging)
    2. Documentan las particularidades de cada API
    3. Facilitan la conversión a PaperMetadata

RATE LIMITS Y AUTENTICACIÓN
===========================

    ┌────────────────────────────────────────────────────────────────────┐
    │ API            │ Rate Limit       │ Auth           │ Notas         │
    ├────────────────┼──────────────────┼────────────────┼───────────────┤
    │ OpenAlex       │ 10 req/s (email) │ Email header   │ Polite pool   │
    │ arXiv          │ 1 req/3s         │ None           │ Bulk: S3      │
    │ Unpaywall      │ 100K/day         │ Email param    │ Solo DOI      │
    │ Semantic S2    │ 100 req/5min     │ API key (opt)  │ Batch API     │
    │ Nobel          │ No limit         │ None           │ Small dataset │
    │ Wikidata       │ No limit         │ None           │ SPARQL        │
    └────────────────────────────────────────────────────────────────────┘

APIs: OpenAlex, arXiv, Unpaywall, Semantic Scholar, PubMed, CrossRef, Nobel, Wikidata.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


# =============================================================================
# MODELO: OPENALEX WORK (RESPUESTA DE OPENALEX)
# =============================================================================

class OpenAlexWork(BaseModel):
    """
    Modelo de respuesta de OpenAlex para un "Work" (paper/artículo).

    ¿QUÉ ES OPENALEX?
    =================

    OpenAlex es el sucesor open-source de Microsoft Academic Graph:

        - 240M+ documentos académicos
        - Licencia CC0 (dominio público)
        - API gratuita sin autenticación
        - Actualización diaria

    URL: https://openalex.org/

    CARACTERÍSTICAS CLAVE
    =====================

        ┌────────────────────────────────────────────────────────────────┐
        │ Aspecto           │ Detalle                                   │
        ├───────────────────┼───────────────────────────────────────────┤
        │ Cobertura         │ 240M+ works, 100M+ autores                │
        │ Actualización     │ Diaria                                    │
        │ Licencia          │ CC0 (sin restricciones)                   │
        │ Rate limit        │ 10 req/s con email, 1 req/s sin           │
        │ Bulk download     │ Snapshots mensuales en S3                 │
        └────────────────────────────────────────────────────────────────┘

    ABSTRACT INVERTED INDEX
    =======================

    OpenAlex almacena abstracts como "inverted index" para ahorrar espacio:

        Formato tradicional:
            "The cat sat on the mat"

        Inverted index:
            {
                "The": [0],
                "cat": [1],
                "sat": [2],
                "on": [3],
                "the": [4],
                "mat": [5]
            }

    El método get_abstract() reconstruye el texto original.

    CONCEPTOS VS TOPICS
    ===================

    OpenAlex tiene dos sistemas de clasificación:

        - concepts: Sistema antiguo (~65K conceptos jerárquicos)
          Ejemplo: "Machine Learning" → "Artificial Intelligence" → "Computer Science"

        - topics: Sistema nuevo (más granular)
          Basado en clustering de papers

    El sistema usa concepts por compatibilidad.

    OpenAlex: 240M+ documents, CC0 license, 10 req/s with email.
    Endpoint: https://api.openalex.org/works

    Attributes:
        id: OpenAlex Work ID (ej: "W2741809807")
        doi: DOI si disponible
        title: Título del paper
        display_name: Nombre para mostrar
        publication_date: Fecha de publicación (string ISO)
        publication_year: Año de publicación
        authorships: Lista de autorías con afiliaciones
        primary_location: Venue principal de publicación
        host_venue: Venue host (deprecated, usar primary_location)
        open_access: Información de acceso abierto
        best_oa_location: Mejor ubicación OA disponible
        concepts: Conceptos asignados (taxonomía OpenAlex)
        topics: Topics asignados (sistema nuevo)
        cited_by_count: Número de citas
        referenced_works_count: Número de referencias
        ids: Identificadores externos (DOI, PMID, etc.)
        abstract_inverted_index: Abstract en formato inverted index
    """

    # -------------------------------------------------------------------------
    # IDENTIFICADORES
    # -------------------------------------------------------------------------

    # OpenAlex Work ID - identificador único en el sistema
    # Formato: "W" + número (ej: "W2741809807")
    # También puede ser URL completo: "https://openalex.org/W2741809807"
    id: str

    # DOI del paper si está disponible
    # Formato: "https://doi.org/10.1038/..." o "10.1038/..."
    # None para papers sin DOI (preprints, tesis, etc.)
    doi: Optional[str] = None

    # Título del paper
    # Puede ser None en casos raros (datos incompletos)
    title: Optional[str] = None

    # Nombre para mostrar (generalmente igual al título)
    # Usado por la UI de OpenAlex
    display_name: Optional[str] = None

    # -------------------------------------------------------------------------
    # FECHAS
    # -------------------------------------------------------------------------

    # Fecha de publicación en formato ISO (YYYY-MM-DD)
    # String porque el día puede faltar: "2023-01" o "2023"
    publication_date: Optional[str] = None

    # Año de publicación como entero
    # Más confiable que publication_date para filtrado
    publication_year: Optional[int] = None

    # -------------------------------------------------------------------------
    # AUTORES
    # -------------------------------------------------------------------------

    # Lista de autorías (no solo autores, incluye afiliaciones)
    # Cada elemento tiene:
    #   - author: {id, display_name, orcid}
    #   - institutions: [{id, display_name, ror, country_code}]
    #   - author_position: "first", "middle", "last"
    authorships: list[dict[str, Any]] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # VENUE/FUENTE
    # -------------------------------------------------------------------------

    # Ubicación principal de publicación
    # Contiene: source (journal/venue), pdf_url, is_oa, license
    # Este es el campo preferido (host_venue está deprecated)
    primary_location: Optional[dict[str, Any]] = None

    # Venue host (DEPRECATED - usar primary_location)
    # Mantenido para retrocompatibilidad con código antiguo
    host_venue: Optional[dict[str, Any]] = None

    # -------------------------------------------------------------------------
    # ACCESO ABIERTO
    # -------------------------------------------------------------------------

    # Información de Open Access
    # Contiene:
    #   - is_oa: bool
    #   - oa_status: "gold", "green", "hybrid", "bronze", "closed"
    #   - oa_url: URL de la versión OA
    open_access: Optional[dict[str, Any]] = None

    # Mejor ubicación OA disponible
    # Contiene: url, pdf_url, version, license
    # Prioriza versiones publicadas sobre preprints
    best_oa_location: Optional[dict[str, Any]] = None

    # -------------------------------------------------------------------------
    # CLASIFICACIÓN
    # -------------------------------------------------------------------------

    # Conceptos asignados (taxonomía jerárquica)
    # Cada concepto tiene:
    #   - id: OpenAlex concept ID
    #   - display_name: "Machine Learning"
    #   - level: 0-5 (0 = más general)
    #   - score: 0-1 (relevancia)
    concepts: list[dict[str, Any]] = Field(default_factory=list)

    # Topics asignados (sistema nuevo, más granular)
    # Estructura similar a concepts pero diferente taxonomía
    topics: list[dict[str, Any]] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # MÉTRICAS
    # -------------------------------------------------------------------------

    # Número de papers que citan este work
    # Actualizado regularmente por OpenAlex
    cited_by_count: Optional[int] = None

    # Número de referencias en la bibliografía
    # Útil para identificar papers de revisión (muchas referencias)
    referenced_works_count: Optional[int] = None

    # -------------------------------------------------------------------------
    # IDENTIFICADORES EXTERNOS
    # -------------------------------------------------------------------------

    # Diccionario de IDs externos
    # Posibles claves: doi, pmid, pmcid, mag (Microsoft Academic)
    # Valores son URLs o IDs crudos dependiendo del campo
    ids: Optional[dict[str, Any]] = None

    # -------------------------------------------------------------------------
    # ABSTRACT
    # -------------------------------------------------------------------------

    # Abstract en formato "inverted index"
    # Formato: {"palabra": [posición1, posición2, ...]}
    # Requiere reconstrucción con get_abstract()
    abstract_inverted_index: Optional[dict[str, list[int]]] = None

    # -------------------------------------------------------------------------
    # MÉTODOS AUXILIARES
    # -------------------------------------------------------------------------

    def get_abstract(self) -> Optional[str]:
        """
        Reconstruye el abstract desde el inverted index.

        ALGORITMO
        =========

        El inverted index mapea palabras a posiciones:

            {"The": [0, 4], "cat": [1], "sat": [2], "on": [3], "mat": [5]}

        Pasos de reconstrucción:
            1. Invertir: [(0, "The"), (1, "cat"), (2, "sat"), ...]
            2. Ordenar por posición
            3. Concatenar palabras con espacios

        COMPLEJIDAD
        ===========

            - Tiempo: O(n log n) donde n = número total de palabras
            - Espacio: O(n) para la lista de palabras

        Returns:
            str: Abstract reconstruido o None si no hay abstract
        """
        # Si no hay abstract, retornar None
        if not self.abstract_inverted_index:
            return None

        # Invertir el índice: de {palabra: [posiciones]} a [(pos, palabra)]
        words: list[tuple[int, str]] = []
        for word, positions in self.abstract_inverted_index.items():
            for pos in positions:
                words.append((pos, word))

        # Ordenar por posición para reconstruir orden original
        words.sort(key=lambda x: x[0])

        # Concatenar palabras con espacios
        return " ".join(word for _, word in words)


# =============================================================================
# MODELO: ARXIV ENTRY (RESPUESTA DE ARXIV)
# =============================================================================

class ArxivEntry(BaseModel):
    """
    Modelo de un paper de arXiv parseado desde el feed Atom.

    ¿QUÉ ES ARXIV?
    ==============

    arXiv es el repositorio de preprints más importante del mundo:

        - Fundado en 1991 por Paul Ginsparg
        - 2.5M+ papers en física, matemáticas, CS, biología, etc.
        - Acceso completamente gratuito
        - Estándar de facto para compartir investigación pre-publicación

    URL: https://arxiv.org/

    SISTEMA DE CATEGORÍAS
    =====================

    arXiv organiza papers en categorías jerárquicas:

        ┌────────────────────────────────────────────────────────────────┐
        │ Área            │ Ejemplos de categorías                      │
        ├─────────────────┼─────────────────────────────────────────────┤
        │ Computer Science│ cs.AI, cs.LG, cs.CL, cs.CV, cs.NE          │
        │ Physics         │ hep-th, cond-mat, quant-ph, astro-ph       │
        │ Mathematics     │ math.CO, math.AG, math.NT                  │
        │ Statistics      │ stat.ML, stat.TH, stat.ME                  │
        │ Economics       │ econ.GN, econ.EM                           │
        │ Biology         │ q-bio.NC, q-bio.PE                         │
        └────────────────────────────────────────────────────────────────┘

    Un paper puede tener múltiples categorías (cross-listed).
    La primary_category es la principal.

    FORMATO DE IDs
    ==============

    arXiv ha tenido dos formatos de IDs:

        Antiguo (pre-2007): category/YYMMNNN
            Ejemplo: hep-th/9905111

        Nuevo (2007+): YYMM.NNNNN
            Ejemplo: 2301.00001

    El sistema acepta ambos formatos.

    API Y RATE LIMITS
    =================

        - Endpoint: http://export.arxiv.org/api/query
        - Formato: Atom feed (XML)
        - Rate limit: 1 request cada 3 segundos
        - Bulk: Amazon S3 (~9.2TB de PDFs)

    arXiv: 2.5M+ papers, no auth, 1 req/3s rate limit.
    Endpoints: http://export.arxiv.org/api/query, S3 bulk (~9.2TB)

    Attributes:
        arxiv_id: Identificador arXiv (ej: "2301.00001")
        title: Título del paper
        summary: Abstract/resumen
        authors: Lista de nombres de autores
        published: Fecha de primera publicación
        updated: Fecha de última actualización
        categories: Lista de categorías arXiv
        primary_category: Categoría principal
        comment: Comentario del autor (páginas, figuras, etc.)
        journal_ref: Referencia si fue publicado en journal
        doi: DOI si fue publicado
        pdf_url: URL directa al PDF
        abs_url: URL de la página del abstract
    """

    # -------------------------------------------------------------------------
    # IDENTIFICACIÓN
    # -------------------------------------------------------------------------

    # arXiv ID - identificador único
    # Formato nuevo: YYMM.NNNNN (ej: "2301.00001")
    # Formato antiguo: category/YYMMNNN (ej: "hep-th/9905111")
    arxiv_id: str

    # -------------------------------------------------------------------------
    # CONTENIDO
    # -------------------------------------------------------------------------

    # Título del paper
    # Puede incluir LaTeX (ej: "Attention is All You $\\alpha$ Need")
    title: str

    # Abstract/resumen del paper
    # Campo llamado "summary" en el API de arXiv
    # Típicamente 1-2 párrafos
    summary: str

    # Lista de nombres de autores
    # Solo nombres, no afiliaciones (arXiv no las incluye en el API)
    # Formato: ["Ashish Vaswani", "Noam Shazeer", ...]
    authors: list[str] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # FECHAS
    # -------------------------------------------------------------------------

    # Fecha de primera publicación en arXiv
    # Es la fecha de la versión v1
    published: datetime

    # Fecha de última actualización
    # Cambia cuando se sube una nueva versión
    # None si nunca se actualizó
    updated: Optional[datetime] = None

    # -------------------------------------------------------------------------
    # CLASIFICACIÓN
    # -------------------------------------------------------------------------

    # Lista de todas las categorías del paper
    # Incluye primary_category y cross-listings
    # Ej: ["cs.AI", "cs.LG", "stat.ML"]
    categories: list[str] = Field(default_factory=list)

    # Categoría principal (la primera al subir)
    # Determina en qué lista diaria aparece
    primary_category: Optional[str] = None

    # -------------------------------------------------------------------------
    # METADATOS ADICIONALES
    # -------------------------------------------------------------------------

    # Comentario del autor
    # Típicamente incluye: número de páginas, figuras, conference
    # Ej: "15 pages, 5 figures, accepted at NeurIPS 2023"
    comment: Optional[str] = None

    # Referencia a journal si fue publicado
    # Ej: "Nature 2023, 1-15"
    # None para papers no publicados
    journal_ref: Optional[str] = None

    # DOI del paper publicado
    # Se añade cuando el preprint se publica en journal
    doi: Optional[str] = None

    # -------------------------------------------------------------------------
    # URLs
    # -------------------------------------------------------------------------

    # URL directa al PDF
    # Formato: https://arxiv.org/pdf/2301.00001.pdf
    pdf_url: str

    # URL de la página del abstract
    # Formato: https://arxiv.org/abs/2301.00001
    abs_url: str


# =============================================================================
# MODELO: UNPAYWALL RESPONSE (RESPUESTA DE UNPAYWALL)
# =============================================================================

class UnpaywallResponse(BaseModel):
    """
    Modelo de respuesta de Unpaywall para encontrar versiones Open Access.

    ¿QUÉ ES UNPAYWALL?
    ==================

    Unpaywall es un servicio que encuentra versiones OA de papers académicos:

        - Indexa 30M+ papers con versiones OA
        - Busca en repositorios, preprint servers, publisher OA
        - Usado por Google Scholar, Zotero, bibliotecas
        - Empresa sin ánimo de lucro (Our Research)

    URL: https://unpaywall.org/

    CÓMO FUNCIONA
    =============

        1. Input: DOI del paper
        2. Unpaywall busca en:
           - Repositorios institucionales
           - PubMed Central
           - arXiv, bioRxiv, etc.
           - Publisher OA (cuando es gold/hybrid)
        3. Output: Lista de ubicaciones OA ordenadas por calidad

    TIPOS DE ACCESO ABIERTO
    =======================

        ┌────────────────────────────────────────────────────────────────┐
        │ Tipo    │ Descripción                │ Ejemplo                 │
        ├─────────┼────────────────────────────┼─────────────────────────┤
        │ Gold    │ Publicado OA en journal    │ PLOS ONE, Nature Comms  │
        │ Green   │ En repositorio             │ arXiv, PubMed Central   │
        │ Hybrid  │ OA en journal de pago      │ Article con APC pagado  │
        │ Bronze  │ Libre pero sin licencia    │ Publisher allows access │
        └────────────────────────────────────────────────────────────────┘

    ORDENAMIENTO DE UBICACIONES
    ===========================

    best_oa_location se elige con esta prioridad:
        1. Versión publicada (VoR) sobre preprint
        2. Con licencia sobre sin licencia
        3. PDF directo sobre landing page
        4. Repositorio estable sobre temporal

    Unpaywall: 100K req/day with email, lookup by DOI.
    Endpoint: https://api.unpaywall.org/v2/{doi}

    Attributes:
        doi: DOI consultado
        is_oa: Si el paper tiene alguna versión OA
        title: Título del paper
        year: Año de publicación
        publisher: Editorial
        journal_name: Nombre del journal
        best_oa_location: Mejor ubicación OA encontrada
        oa_locations: Todas las ubicaciones OA disponibles
    """

    # -------------------------------------------------------------------------
    # IDENTIFICACIÓN
    # -------------------------------------------------------------------------

    # DOI consultado (echo del input)
    # Formato: "10.1038/nature12373" (sin https://doi.org/)
    doi: str

    # Flag indicando si hay alguna versión OA
    # True si oa_locations no está vacío
    is_oa: bool

    # -------------------------------------------------------------------------
    # METADATOS BÁSICOS
    # -------------------------------------------------------------------------

    # Título del paper
    # Obtenido de CrossRef o del publisher
    title: Optional[str] = None

    # Año de publicación
    year: Optional[int] = None

    # Editorial
    # Ej: "Elsevier", "Springer Nature", "IEEE"
    publisher: Optional[str] = None

    # Nombre del journal
    # Ej: "Nature", "Science", "PLOS ONE"
    journal_name: Optional[str] = None

    # -------------------------------------------------------------------------
    # UBICACIONES OA
    # -------------------------------------------------------------------------

    # Mejor ubicación OA según algoritmo de Unpaywall
    # Contiene:
    #   - url: Landing page
    #   - url_for_pdf: URL directa al PDF (preferida)
    #   - evidence: Cómo se encontró ("open", "oa repository", etc.)
    #   - host_type: "publisher", "repository"
    #   - version: "publishedVersion", "acceptedVersion", "submittedVersion"
    #   - license: "cc-by", "cc0", etc.
    best_oa_location: Optional[dict[str, Any]] = None

    # Todas las ubicaciones OA encontradas
    # Lista ordenada por calidad (mejor primero)
    # Útil si best_oa_location no tiene PDF directo
    oa_locations: list[dict[str, Any]] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # MÉTODOS AUXILIARES
    # -------------------------------------------------------------------------

    def get_pdf_url(self) -> Optional[str]:
        """
        Obtiene la mejor URL de PDF disponible.

        LÓGICA
        ======

        1. Primero intenta best_oa_location.url_for_pdf
        2. Si no hay PDF directo, retorna None
           (no retorna landing page porque no es útil para descarga automática)

        Returns:
            str: URL directa al PDF o None
        """
        if self.best_oa_location:
            return self.best_oa_location.get("url_for_pdf")
        return None


# =============================================================================
# MODELO: SEMANTIC SCHOLAR PAPER (RESPUESTA DE S2)
# =============================================================================

class SemanticScholarPaper(BaseModel):
    """
    Modelo de paper de Semantic Scholar API.

    ¿QUÉ ES SEMANTIC SCHOLAR?
    =========================

    Semantic Scholar (S2) es un motor de búsqueda académico de AI2:

        - 200M+ papers indexados
        - Features de IA: TLDR, influencia, conceptos
        - Citation graph completo
        - API gratuita con límites generosos

    URL: https://www.semanticscholar.org/

    CARACTERÍSTICAS ÚNICAS
    ======================

        ┌────────────────────────────────────────────────────────────────┐
        │ Feature         │ Descripción                                 │
        ├─────────────────┼─────────────────────────────────────────────┤
        │ TLDR            │ Resumen de 1 oración generado por IA       │
        │ Influential     │ Citas que realmente usan/extienden el paper│
        │ Citation Intent │ Clasificación de citas (background, method)│
        │ fieldsOfStudy   │ Campos asignados automáticamente           │
        └────────────────────────────────────────────────────────────────┘

    IDs EN SEMANTIC SCHOLAR
    =======================

    S2 tiene dos tipos de IDs:

        - paperId: Hash de 40 caracteres (interno)
          Ej: "649def34f8be52c8b66281af98ae884c09aef38b"

        - corpusId: Numérico, más estable para referencias
          Ej: 12345678

    RATE LIMITS
    ===========

        - Sin API key: 100 requests / 5 minutos
        - Con API key: 1 request / segundo (burst de 10)
        - Batch API: 500 papers por request

    S2: 200M+ papers, 100 req/5min (optional API key).
    Endpoint: https://api.semanticscholar.org/graph/v1/paper

    Attributes:
        paperId: ID interno de S2 (hash 40 chars)
        corpusId: ID numérico del corpus
        externalIds: IDs externos (DOI, arXiv, PMID)
        title: Título del paper
        abstract: Abstract del paper
        year: Año de publicación
        authors: Lista de autores con IDs
        venue: Venue de publicación
        citationCount: Número de citas
        referenceCount: Número de referencias
        isOpenAccess: Si hay versión OA
        openAccessPdf: Info del PDF OA
        fieldsOfStudy: Campos asignados por IA
    """

    # -------------------------------------------------------------------------
    # IDENTIFICADORES
    # -------------------------------------------------------------------------

    # ID interno de Semantic Scholar
    # Hash SHA1 de 40 caracteres hexadecimales
    # Único y estable para cada paper
    paperId: str

    # ID numérico del corpus
    # Más fácil de usar en URLs y referencias
    corpusId: Optional[int] = None

    # IDs externos mapeados
    # Claves posibles: DOI, ArXiv, PubMed, MAG, ACL, DBLP
    # Ej: {"DOI": "10.1038/...", "ArXiv": "2301.00001"}
    externalIds: Optional[dict[str, str]] = None

    # -------------------------------------------------------------------------
    # CONTENIDO
    # -------------------------------------------------------------------------

    # Título del paper
    title: Optional[str] = None

    # Abstract del paper
    # A diferencia de OpenAlex, viene en texto plano
    abstract: Optional[str] = None

    # Año de publicación
    year: Optional[int] = None

    # -------------------------------------------------------------------------
    # AUTORES
    # -------------------------------------------------------------------------

    # Lista de autores con sus IDs de S2
    # Cada elemento tiene:
    #   - authorId: ID interno de S2
    #   - name: Nombre del autor
    authors: list[dict[str, Any]] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # VENUE/FUENTE
    # -------------------------------------------------------------------------

    # Venue de publicación
    # Puede ser journal, conferencia, o workshop
    # Ej: "Nature", "NeurIPS", "arXiv.org"
    venue: Optional[str] = None

    # -------------------------------------------------------------------------
    # MÉTRICAS
    # -------------------------------------------------------------------------

    # Número de citas según S2
    # Puede diferir ligeramente de OpenAlex
    citationCount: Optional[int] = None

    # Número de referencias en bibliografía
    referenceCount: Optional[int] = None

    # -------------------------------------------------------------------------
    # ACCESO ABIERTO
    # -------------------------------------------------------------------------

    # Flag indicando si hay versión OA
    isOpenAccess: Optional[bool] = None

    # Información del PDF OA
    # Contiene: url, status (posible: "LEGAL", "ILLEGAL")
    openAccessPdf: Optional[dict[str, str]] = None

    # -------------------------------------------------------------------------
    # CLASIFICACIÓN
    # -------------------------------------------------------------------------

    # Campos de estudio asignados por IA
    # Ej: ["Computer Science", "Medicine"]
    # Más amplio que las categorías arXiv
    fieldsOfStudy: list[str] = Field(default_factory=list)


# =============================================================================
# MODELO: NOBEL LAUREATE (RESPUESTA DEL API DE NOBEL)
# =============================================================================

class NobelLaureate(BaseModel):
    """
    Modelo de laureado Nobel desde el API oficial.

    ¿QUÉ ES EL API DE NOBEL?
    ========================

    La Fundación Nobel ofrece un API público con todos los premios:

        - Datos desde 1901 hasta el presente
        - Información de premios, laureados, motivaciones
        - Sin autenticación requerida
        - Datos multilingües (inglés, sueco, noruego)

    URL: https://api.nobelprize.org/

    ESTRUCTURA DE DATOS
    ===================

        ┌────────────────────────────────────────────────────────────────┐
        │ Entidad      │ Descripción                                    │
        ├──────────────┼────────────────────────────────────────────────┤
        │ Laureate     │ Persona u organización premiada               │
        │ Nobel Prize  │ Premio específico (física 2023, paz 1990)     │
        │ Motivation   │ Razón del premio (en múltiples idiomas)       │
        │ Affiliation  │ Institución al momento del premio             │
        └────────────────────────────────────────────────────────────────┘

    CAMPOS MULTILINGÜES
    ===================

    Muchos campos vienen en formato multilingüe:

        {
            "knownName": {
                "en": "Albert Einstein",
                "se": "Albert Einstein"
            }
        }

    El método get_name() extrae el nombre en el idioma deseado.

    CATEGORÍAS DE PREMIOS
    =====================

        - Physics (phy)
        - Chemistry (che)
        - Medicine (med) - oficialmente "Physiology or Medicine"
        - Literature (lit)
        - Peace (pea)
        - Economic Sciences (eco) - desde 1969

    Nobel API: api.nobelprize.org/2.1/, no auth, full data since 1901.

    Attributes:
        id: ID interno del API Nobel
        knownName: Nombre conocido en múltiples idiomas
        givenName: Nombre de pila en múltiples idiomas
        familyName: Apellido en múltiples idiomas
        fullName: Nombre completo en múltiples idiomas
        gender: Género ("male", "female", "org" para organizaciones)
        birth: Información de nacimiento
        death: Información de fallecimiento (si aplica)
        nobelPrizes: Lista de premios Nobel recibidos
    """

    # -------------------------------------------------------------------------
    # IDENTIFICACIÓN
    # -------------------------------------------------------------------------

    # ID interno del API Nobel
    # Numérico como string (ej: "123")
    id: str

    # -------------------------------------------------------------------------
    # NOMBRES (MULTILINGÜES)
    # -------------------------------------------------------------------------

    # Nombre conocido/común
    # Formato: {"en": "Albert Einstein", "se": "Albert Einstein"}
    knownName: Optional[dict[str, str]] = None

    # Nombre de pila
    # Formato: {"en": "Albert", "se": "Albert"}
    givenName: Optional[dict[str, str]] = None

    # Apellido
    # Formato: {"en": "Einstein", "se": "Einstein"}
    familyName: Optional[dict[str, str]] = None

    # Nombre completo formal
    # Usado en citaciones oficiales
    fullName: Optional[dict[str, str]] = None

    # -------------------------------------------------------------------------
    # INFORMACIÓN PERSONAL
    # -------------------------------------------------------------------------

    # Género del laureado
    # Valores: "male", "female", "org" (para organizaciones como CERN, ONU)
    gender: Optional[str] = None

    # Información de nacimiento
    # Contiene: date (ISO), place {city, country}
    birth: Optional[dict[str, Any]] = None

    # Información de fallecimiento (si aplica)
    # Mismo formato que birth
    # None si el laureado sigue vivo
    death: Optional[dict[str, Any]] = None

    # -------------------------------------------------------------------------
    # PREMIOS
    # -------------------------------------------------------------------------

    # Lista de premios Nobel recibidos
    # Un laureado puede tener múltiples (ej: Marie Curie)
    # Cada premio contiene:
    #   - awardYear: Año del premio
    #   - category: Categoría (phy, che, med, lit, pea, eco)
    #   - categoryFullName: Nombre completo
    #   - motivation: Razón del premio (multilingüe)
    #   - prizeAmount: Monto del premio
    #   - affiliations: Instituciones al momento del premio
    nobelPrizes: list[dict[str, Any]] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # MÉTODOS AUXILIARES
    # -------------------------------------------------------------------------

    def get_name(self, lang: str = "en") -> str:
        """
        Obtiene el nombre del laureado en el idioma especificado.

        PRIORIDAD
        =========

        1. fullName (nombre completo formal)
        2. knownName (nombre común)
        3. "Unknown" como fallback

        Args:
            lang: Código de idioma ("en", "se", "no")

        Returns:
            str: Nombre en el idioma solicitado
        """
        # Intentar nombre completo primero
        if self.fullName and lang in self.fullName:
            return self.fullName[lang]

        # Fallback a nombre conocido
        if self.knownName and lang in self.knownName:
            return self.knownName[lang]

        # Último recurso
        return "Unknown"


# =============================================================================
# MODELO: WIKIDATA ENTITY (ENTIDAD DE WIKIDATA)
# =============================================================================

class WikidataEntity(BaseModel):
    """
    Modelo de entidad Wikidata para premios científicos.

    ¿QUÉ ES WIKIDATA?
    =================

    Wikidata es la base de conocimiento estructurado de Wikimedia:

        - 100M+ entidades (personas, lugares, conceptos)
        - Datos enlazados (linked data)
        - Actualización colaborativa en tiempo real
        - Licencia CC0 (dominio público)
        - API SPARQL para queries complejas

    URL: https://www.wikidata.org/

    IDENTIFICADORES Q-ID
    ====================

    Cada entidad tiene un identificador único:

        ┌────────────────────────────────────────────────────────────────┐
        │ Q-ID       │ Entidad                                          │
        ├────────────┼──────────────────────────────────────────────────┤
        │ Q937       │ Albert Einstein                                  │
        │ Q28835     │ Fields Medal                                     │
        │ Q185667    │ Turing Award                                     │
        │ Q160042    │ Abel Prize                                       │
        │ Q7191      │ Nobel Prize                                      │
        │ Q2793400   │ Wolf Prize in Mathematics                        │
        └────────────────────────────────────────────────────────────────┘

    SPARQL ENDPOINT
    ===============

    Las queries se hacen vía SPARQL:

        ```sparql
        SELECT ?person ?personLabel
        WHERE {
          ?person wdt:P166 wd:Q28835.  # received award = Fields Medal
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        ```

    Endpoint: https://query.wikidata.org/sparql

    USO EN EL SISTEMA
    =================

    Usamos Wikidata para obtener ganadores de premios no cubiertos
    por APIs específicas:

        - Fields Medal (matemáticas)
        - Turing Award (computación)
        - Abel Prize (matemáticas)
        - Wolf Prize (matemáticas, física)
        - Breakthrough Prize (física, matemáticas, life sciences)

    Wikidata SPARQL: query.wikidata.org/sparql, no auth.
    IDs: Fields Medal (Q28835), Turing Award (Q185667), Abel Prize (Q160042), etc.

    Attributes:
        qid: Identificador Wikidata (ej: "Q937")
        label: Nombre de la entidad
        description: Descripción corta
        aliases: Nombres alternativos
        award_date: Fecha del premio (si es ganador)
        award_id: Q-ID del premio
        affiliation: Afiliación al momento del premio
    """

    # -------------------------------------------------------------------------
    # IDENTIFICACIÓN
    # -------------------------------------------------------------------------

    # Q-ID de Wikidata - identificador único global
    # Formato: "Q" + número (ej: "Q937" para Einstein)
    qid: str

    # -------------------------------------------------------------------------
    # INFORMACIÓN BÁSICA
    # -------------------------------------------------------------------------

    # Etiqueta/nombre de la entidad
    # Depende del idioma de la query (normalmente inglés)
    label: str

    # Descripción corta de la entidad
    # Ej: "German-born theoretical physicist"
    description: Optional[str] = None

    # Nombres alternativos/aliases
    # Ej: ["Albert E.", "A. Einstein"]
    aliases: list[str] = Field(default_factory=list)

    # -------------------------------------------------------------------------
    # INFORMACIÓN DE PREMIO (si es ganador de premio)
    # -------------------------------------------------------------------------

    # Fecha en que recibió el premio
    # Extraída de la propiedad P585 (point in time)
    award_date: Optional[datetime] = None

    # Q-ID del premio recibido
    # Ej: "Q28835" para Fields Medal
    # Útil para agrupar por tipo de premio
    award_id: Optional[str] = None

    # Afiliación al momento del premio
    # Extraída de qualifiers de la propiedad P166 (award received)
    affiliation: Optional[str] = None
