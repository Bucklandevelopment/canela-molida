"""
================================================================================
SERVICIO DE PROCESAMIENTO PDF - GROBID + PYMUPDF4LLM
================================================================================

Este módulo implementa la extracción de contenido de PDFs científicos usando
una combinación de herramientas especializadas para obtener metadatos
estructurados y texto optimizado para RAG.

DESAFÍO DEL PDF CIENTÍFICO
==========================

Los PDFs científicos son particularmente difíciles de procesar:

    ┌────────────────────────────────────────────────────────────────────────┐
    │                  ANATOMÍA DE UN PDF CIENTÍFICO                         │
    │                                                                        │
    │   ┌────────────────────────────────────────────────────────────────┐  │
    │   │ HEADER: Título, autores, afiliaciones, email                   │  │
    │   │ (2 columnas, fuentes variadas, logos institucionales)          │  │
    │   ├────────────────────────────────────────────────────────────────┤  │
    │   │ ABSTRACT: Texto estructurado con keywords                      │  │
    │   ├─────────────────────┬──────────────────────────────────────────┤  │
    │   │ Columna 1           │ Columna 2                                │  │
    │   │ - Ecuaciones LaTeX  │ - Figuras con caption                    │  │
    │   │ - Tablas complejas  │ - Referencias cruzadas                   │  │
    │   │ - Footnotes         │ - Código/algoritmos                      │  │
    │   ├─────────────────────┴──────────────────────────────────────────┤  │
    │   │ REFERENCIAS: Formato variado (APA, IEEE, Chicago, etc.)        │  │
    │   └────────────────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────────────────┘

ESTRATEGIA DE DOS HERRAMIENTAS
==============================

El sistema combina dos herramientas complementarias:

    ┌────────────────────────────────────────────────────────────────────────┐
    │            GROBID                    vs           PyMuPDF4LLM          │
    │     (metadatos estructurados)               (texto para RAG)           │
    │                                                                        │
    │   ┌─────────────────────────┐        ┌─────────────────────────┐      │
    │   │ • Machine Learning      │        │ • Procesamiento rápido  │      │
    │   │ • F1-score 0.87-0.90    │        │ • 0.12s por documento   │      │
    │   │ • 55+ campos TEI-XML    │        │ • Output Markdown       │      │
    │   │ • 2-3 segundos/doc      │        │ • Preserva estructura   │      │
    │   │ • Requiere servidor     │        │ • Sin GPU necesaria     │      │
    │   │ • Docker: 8GB RAM       │        │ • Librería local        │      │
    │   └─────────────────────────┘        └─────────────────────────┘      │
    │                                                                        │
    │   USO: Extraer título,            USO: Extraer texto completo          │
    │        autores, DOI, refs              para vectorización              │
    └────────────────────────────────────────────────────────────────────────┘

¿QUÉ ES GROBID?
===============

GROBID (GeneRation Of BIbliographic Data) es un sistema ML para PDFs:

    - Desarrollado por INRIA (Francia)
    - Usado por CrossRef, ResearchGate, Semantic Scholar
    - Entrenado en millones de papers
    - Output en TEI-XML (Text Encoding Initiative)

    CAMPOS TEI-XML EXTRAÍDOS (55+):
    ─────────────────────────────────
    • Título, subtítulo
    • Autores con afiliaciones
    • Abstract
    • Keywords
    • DOI, ISSN, ISBN
    • Fecha de publicación
    • Journal/conferencia
    • Referencias bibliográficas (estructuradas)
    • Funding information
    • Y muchos más...

¿QUÉ ES PYMUPDF4LLM?
====================

PyMuPDF4LLM es una extensión de PyMuPDF optimizada para LLMs:

    ┌────────────────────────────────────────────────────────────────────┐
    │ Característica     │ PyMuPDF4LLM    │ PyPDF2/pdfplumber         │
    ├────────────────────┼────────────────┼───────────────────────────┤
    │ Velocidad          │ 0.12s/doc      │ 0.5-2s/doc                │
    │ Output             │ Markdown       │ Plain text                │
    │ Headers            │ Preservados    │ Perdidos                  │
    │ Tablas             │ Formato MD     │ Texto plano               │
    │ Layout             │ Respetado      │ A menudo mezclado         │
    │ LLM-ready          │ ✓              │ Requiere post-proceso     │
    └────────────────────────────────────────────────────────────────────┘

ESTRATEGIA DE CHUNKING
======================

El chunking es crítico para la calidad del RAG:

    ┌────────────────────────────────────────────────────────────────────────┐
    │                    CHUNKING RECURSIVO JERÁRQUICO                       │
    │                                                                        │
    │   Documento completo (50,000 caracteres)                              │
    │                    │                                                   │
    │                    ▼ Separador: "\\n\\n" (párrafos)                    │
    │   ┌─────────────────────────────────────────────────────────────────┐ │
    │   │ Párrafo 1 │ Párrafo 2 │ ... │ Párrafo N │                       │ │
    │   └─────────────────────────────────────────────────────────────────┘ │
    │                    │                                                   │
    │                    ▼ Si párrafo > 1000 chars, separador: "\\n"        │
    │   ┌─────────────────────────────────────────────────────────────────┐ │
    │   │ Línea 1 │ Línea 2 │ ... │ Línea M │                             │ │
    │   └─────────────────────────────────────────────────────────────────┘ │
    │                    │                                                   │
    │                    ▼ Si línea > 1000 chars, separador: ". "           │
    │   ┌─────────────────────────────────────────────────────────────────┐ │
    │   │ Oración 1 │ Oración 2 │ ... │                                   │ │
    │   └─────────────────────────────────────────────────────────────────┘ │
    │                                                                        │
    │   OVERLAP: 200 caracteres entre chunks consecutivos                   │
    │   ───────────────────────────────────────────────────                 │
    │   Chunk N:   [...texto......................|overlap]                 │
    │   Chunk N+1:                        [overlap|...texto..............]  │
    └────────────────────────────────────────────────────────────────────────┘

NOUGAT (OPCIONAL)
=================

Para papers con muchas ecuaciones, Nougat es superior:

    - 75% BLEU score en ecuaciones
    - Convierte PDF → LaTeX
    - Requiere GPU (~4.2GB VRAM)
    - Más lento (~10s/página)

    No incluido por defecto (requiere GPU potente).

GROBID: Structured metadata extraction (F1-score 0.87-0.90)
- 55+ TEI-XML fields
- 2-3s per document
- Excellent for references, authors, affiliations
- Docker: grobid/grobid:0.8.2-full

PyMuPDF4LLM: Fast text extraction for RAG (0.12s/doc)
- Markdown output with headers and tables
- Best for general RAG pipelines
- No GPU required

Nougat (optional): Best for mathematical equations (75% BLEU)
- Converts equations to LaTeX
- Requires GPU (~4.2GB VRAM)
"""

# =============================================================================
# IMPORTS
# =============================================================================

import asyncio                      # Para operaciones async con GROBID
import re                           # Para detección de secciones
import xml.etree.ElementTree as ET  # Para parsear TEI-XML de GROBID
from functools import lru_cache     # Singleton pattern
from pathlib import Path
from typing import Optional, Any

import httpx                        # Cliente HTTP async para GROBID
import pymupdf4llm                  # Extracción de texto optimizada para LLM

from app.core.config import get_settings
from app.models.paper import PaperMetadata, Author, PaperChunk


# =============================================================================
# CONSTANTES
# =============================================================================

# Namespace TEI para parsear output XML de GROBID
# TEI (Text Encoding Initiative) es el formato estándar de GROBID
# Todos los elementos en el XML usan este namespace
TEI_NS = "{http://www.tei-c.org/ns/1.0}"


# =============================================================================
# CLASE: PDF PROCESSOR
# =============================================================================

class PDFProcessor:
    """
    Servicio de procesamiento PDF combinando GROBID y PyMuPDF4LLM.

    ARQUITECTURA
    ============

    El procesamiento sigue un pipeline de dos etapas:

        ┌─────────────────────────────────────────────────────────────────┐
        │                    PIPELINE DE PROCESAMIENTO                     │
        │                                                                  │
        │   PDF Input                                                      │
        │       │                                                          │
        │       ├──────────────────┐                                       │
        │       ▼                  ▼                                       │
        │   ┌────────┐        ┌────────────┐                               │
        │   │ GROBID │        │ PyMuPDF4LLM│                               │
        │   │        │        │            │                               │
        │   │ → DOI  │        │ → Markdown │                               │
        │   │ → Title│        │ → Headers  │                               │
        │   │ → Auth.│        │ → Tables   │                               │
        │   └────┬───┘        └──────┬─────┘                               │
        │        │                   │                                      │
        │        ▼                   ▼                                      │
        │   ┌──────────────────────────────┐                               │
        │   │       CHUNKING RECURSIVO     │                               │
        │   │   1000 chars, 200 overlap    │                               │
        │   └──────────────────────────────┘                               │
        │                   │                                               │
        │                   ▼                                               │
        │   ┌──────────────────────────────┐                               │
        │   │     VECTOR STORE (LanceDB)   │                               │
        │   └──────────────────────────────┘                               │
        └─────────────────────────────────────────────────────────────────┘

    USO TÍPICO
    ==========

        >>> processor = PDFProcessor()
        >>>
        >>> # Procesar PDF completo
        >>> result = await processor.process_pdf("paper.pdf", "paper-123")
        >>> print(result["chunks"])  # Lista de chunks para vectorización

        >>> # O paso a paso:
        >>> metadata = await processor.extract_metadata_grobid("paper.pdf")
        >>> markdown = processor.extract_text("paper.pdf")
        >>> chunks = processor.create_chunks(markdown, "paper-123")

    Usage:
        processor = PDFProcessor()

        # Extract structured metadata with GROBID
        metadata = await processor.extract_metadata("paper.pdf")

        # Extract text for RAG with PyMuPDF4LLM
        markdown = processor.extract_text("paper.pdf")

        # Create chunks for vector store
        chunks = processor.create_chunks(markdown, paper_id="123")
    """

    # -------------------------------------------------------------------------
    # INICIALIZACIÓN
    # -------------------------------------------------------------------------

    def __init__(
        self,
        grobid_url: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """
        Inicializa el procesador de PDFs.

        PARÁMETROS
        ==========

        grobid_url: URL del servidor GROBID
        -----------------------------------
            Default: http://localhost:8070
            Docker: http://grobid:8070 (nombre del servicio)

            GROBID corre como servicio separado porque:
            - Requiere ~8GB RAM
            - Tiene modelos ML grandes
            - Beneficia de persistencia

        chunk_size: Tamaño de cada chunk en caracteres
        -----------------------------------------------
            Default: 1000 (recomendado para papers científicos)

            Consideraciones:
            - <500: Pierde contexto semántico
            - >2000: Diluye relevancia en búsqueda
            - 1000 ≈ 1 párrafo científico ≈ 250 tokens

        chunk_overlap: Solapamiento entre chunks
        ----------------------------------------
            Default: 200 caracteres (20% del chunk)

            Propósito:
            - Preservar contexto en boundaries
            - Evitar cortar conceptos a mitad
            - Mejorar coherencia en retrieval

        Args:
            grobid_url: GROBID server URL (default: http://localhost:8070)
            chunk_size: Character size for text chunks (default: 1000)
            chunk_overlap: Overlap between chunks (default: 200)
        """
        # Obtener configuración global
        settings = get_settings()

        # ---------------------------------------------------------------------
        # CONFIGURACIÓN DE GROBID
        # ---------------------------------------------------------------------

        # URL del servidor GROBID
        self.grobid_url = grobid_url or settings.grobid_url

        # Timeout para requests a GROBID (papers grandes pueden tardar)
        self.grobid_timeout = settings.grobid_timeout

        # ---------------------------------------------------------------------
        # CONFIGURACIÓN DE CHUNKING
        # ---------------------------------------------------------------------

        # Parámetros de chunking (siguiendo guía técnica)
        # chunk_size: 1000 caracteres es óptimo para BGE-M3
        self.chunk_size = chunk_size or settings.chunk_size

        # chunk_overlap: 200 caracteres asegura continuidad semántica
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

        # Separadores jerárquicos para chunking recursivo
        # Orden de prioridad: párrafos → líneas → oraciones → palabras
        self.chunk_separators = settings.chunk_separators

        # ---------------------------------------------------------------------
        # CLIENTE HTTP ASYNC
        # ---------------------------------------------------------------------

        # httpx.AsyncClient para requests async a GROBID
        # Timeout alto porque GROBID puede tardar en papers largos
        self._client = httpx.AsyncClient(timeout=self.grobid_timeout)

    # -------------------------------------------------------------------------
    # MÉTODOS DE CICLO DE VIDA
    # -------------------------------------------------------------------------

    async def close(self) -> None:
        """
        Cierra el cliente HTTP.

        CUÁNDO LLAMAR
        =============

        Llamar al finalizar el uso del procesador:

            processor = PDFProcessor()
            try:
                result = await processor.process_pdf(...)
            finally:
                await processor.close()

        O usar context manager (si se implementa).
        """
        await self._client.aclose()

    # -------------------------------------------------------------------------
    # MÉTODOS DE GROBID
    # -------------------------------------------------------------------------

    async def is_grobid_available(self) -> bool:
        """
        Verifica si el servidor GROBID está disponible.

        ENDPOINT
        ========

        GET /api/isalive

        Retorna 200 si GROBID está operativo.

        USO
        ===

        Verificar antes de intentar extraer metadatos:

            if await processor.is_grobid_available():
                metadata = await processor.extract_metadata_grobid(pdf)
            else:
                # Fallback: usar solo PyMuPDF4LLM
                markdown = processor.extract_text(pdf)

        Returns:
            bool: True si GROBID está disponible
        """
        try:
            response = await self._client.get(
                f"{self.grobid_url}/api/isalive",
                timeout=5.0,  # Timeout corto para health check
            )
            return response.status_code == 200
        except Exception:
            return False

    async def extract_metadata_grobid(
        self,
        pdf_path: Path,
    ) -> Optional[PaperMetadata]:
        """
        Extrae metadatos estructurados usando GROBID.

        ENDPOINT DE GROBID
        ==================

        POST /api/processFulltextDocument

        Parámetros:
        - input: Archivo PDF
        - consolidateHeader: "1" (mejorar extracción de header)
        - consolidateCitations: "1" (resolver referencias)

        CAMPOS EXTRAÍDOS
        ================

        Del TEI-XML de GROBID, extraemos:

            ┌────────────────────────────────────────────────────────┐
            │ Campo          │ XPath TEI                            │
            ├────────────────┼──────────────────────────────────────┤
            │ Título         │ //titleStmt/title                    │
            │ Abstract       │ //abstract/p                         │
            │ Autores        │ //author/persName                    │
            │ Afiliaciones   │ //author//affiliation/orgName        │
            │ DOI            │ //idno[@type="DOI"]                  │
            │ Año            │ //publicationStmt/date/@when         │
            │ Journal        │ //monogr/title                       │
            └────────────────────────────────────────────────────────┘

        F1-SCORE
        ========

        GROBID alcanza F1-score de 0.87-0.90 en:
        - Extracción de referencias
        - Parsing de autores
        - Detección de afiliaciones

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            PaperMetadata si exitoso, None si falla
        """
        # Verificar disponibilidad de GROBID
        if not await self.is_grobid_available():
            return None

        try:
            # Leer archivo PDF
            with open(pdf_path, "rb") as f:
                # Enviar a GROBID
                response = await self._client.post(
                    f"{self.grobid_url}/api/processFulltextDocument",
                    files={"input": f},
                    data={
                        # Consolidar header mejora extracción de metadatos
                        "consolidateHeader": "1",
                        # Consolidar citas resuelve referencias
                        "consolidateCitations": "1",
                    },
                )
                response.raise_for_status()

            # Parsear TEI-XML a PaperMetadata
            return self._parse_tei_xml(response.text)

        except Exception:
            # Si falla, retornar None (el caller puede usar fallback)
            return None

    def _parse_tei_xml(self, xml_text: str) -> PaperMetadata:
        """
        Parsea el output TEI-XML de GROBID a PaperMetadata.

        TEI-XML STRUCTURE
        =================

        GROBID produce XML con esta estructura simplificada:

            <TEI>
              <teiHeader>
                <fileDesc>
                  <titleStmt>
                    <title>Paper Title</title>
                  </titleStmt>
                  <publicationStmt>
                    <date when="2023"/>
                  </publicationStmt>
                  <sourceDesc>
                    <biblStruct>
                      <analytic>
                        <author>
                          <persName>
                            <forename>John</forename>
                            <surname>Doe</surname>
                          </persName>
                          <affiliation>
                            <orgName>MIT</orgName>
                          </affiliation>
                        </author>
                      </analytic>
                      <monogr>
                        <title>Nature</title>
                        <idno type="DOI">10.1038/...</idno>
                      </monogr>
                    </biblStruct>
                  </sourceDesc>
                </fileDesc>
                <profileDesc>
                  <abstract>
                    <p>Abstract text...</p>
                  </abstract>
                </profileDesc>
              </teiHeader>
            </TEI>

        Args:
            xml_text: XML string de GROBID

        Returns:
            PaperMetadata con los campos extraídos
        """
        # Parsear XML
        root = ET.fromstring(xml_text)

        # ---------------------------------------------------------------------
        # EXTRAER TÍTULO
        # ---------------------------------------------------------------------

        title_elem = root.find(f".//{TEI_NS}titleStmt/{TEI_NS}title")
        title = title_elem.text if title_elem is not None else "Untitled"

        # ---------------------------------------------------------------------
        # EXTRAER ABSTRACT
        # ---------------------------------------------------------------------

        abstract_elem = root.find(f".//{TEI_NS}abstract/{TEI_NS}p")
        abstract = abstract_elem.text if abstract_elem is not None else None

        # ---------------------------------------------------------------------
        # EXTRAER AUTORES CON AFILIACIONES
        # ---------------------------------------------------------------------

        authors = []
        for author_elem in root.findall(f".//{TEI_NS}author"):
            # Buscar nombre dentro de <persName>
            persname = author_elem.find(f"{TEI_NS}persName")
            if persname is not None:
                # Extraer forename (nombre) y surname (apellido)
                forename = persname.find(f"{TEI_NS}forename")
                surname = persname.find(f"{TEI_NS}surname")

                name_parts = []
                if forename is not None and forename.text:
                    name_parts.append(forename.text)
                if surname is not None and surname.text:
                    name_parts.append(surname.text)

                if name_parts:
                    # Buscar afiliación
                    affiliation = None
                    aff_elem = author_elem.find(f".//{TEI_NS}affiliation/{TEI_NS}orgName")
                    if aff_elem is not None:
                        affiliation = aff_elem.text

                    # Crear objeto Author
                    authors.append(
                        Author(
                            name=" ".join(name_parts),
                            affiliation=affiliation,
                        )
                    )

        # ---------------------------------------------------------------------
        # EXTRAER DOI
        # ---------------------------------------------------------------------

        doi = None
        for idno in root.findall(f".//{TEI_NS}idno"):
            if idno.get("type") == "DOI":
                doi = idno.text
                break

        # ---------------------------------------------------------------------
        # EXTRAER AÑO DE PUBLICACIÓN
        # ---------------------------------------------------------------------

        date_elem = root.find(f".//{TEI_NS}publicationStmt/{TEI_NS}date")
        year = None
        if date_elem is not None:
            # El atributo @when contiene la fecha
            when = date_elem.get("when")
            if when:
                try:
                    # Extraer solo el año (primeros 4 caracteres)
                    year = int(when[:4])
                except ValueError:
                    pass

        # ---------------------------------------------------------------------
        # EXTRAER JOURNAL
        # ---------------------------------------------------------------------

        journal_elem = root.find(f".//{TEI_NS}monogr/{TEI_NS}title")
        journal = journal_elem.text if journal_elem is not None else None

        # ---------------------------------------------------------------------
        # CONSTRUIR Y RETORNAR PAPERMETADATA
        # ---------------------------------------------------------------------

        return PaperMetadata(
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            journal=journal,
            source_api="grobid",  # Marcar origen para trazabilidad
        )

    # -------------------------------------------------------------------------
    # MÉTODOS DE PYMUPDF4LLM
    # -------------------------------------------------------------------------

    def extract_text(self, pdf_path: Path) -> str:
        """
        Extrae texto del PDF usando PyMuPDF4LLM.

        VENTAJAS DE PYMUPDF4LLM
        =======================

        Comparado con otras librerías de extracción:

            ┌────────────────────────────────────────────────────────┐
            │ Característica  │ PyMuPDF4LLM │ pdfplumber │ PyPDF2   │
            ├─────────────────┼─────────────┼────────────┼──────────┤
            │ Velocidad       │ 0.12s/doc   │ ~1s/doc    │ ~0.5s    │
            │ Formato output  │ Markdown    │ Text       │ Text     │
            │ Headers         │ # H1, ## H2 │ ✗          │ ✗        │
            │ Tablas          │ |col|col|   │ ✓          │ ✗        │
            │ Layout 2-col    │ Respetado   │ Mezclado   │ Mezclado │
            │ LLM-optimized   │ ✓           │ ✗          │ ✗        │
            └────────────────────────────────────────────────────────┘

        OUTPUT MARKDOWN
        ===============

        El output incluye:
        - Headers con niveles (# ## ###)
        - Listas con bullets
        - Tablas en formato markdown
        - Preservación de estructura

        PyMuPDF4LLM is optimized for RAG:
        - 0.12s per document (10x faster than Nougat)
        - Markdown output preserving structure
        - Handles tables and headers

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            Texto en formato Markdown
        """
        # to_markdown() convierte PDF a Markdown optimizado para LLMs
        return pymupdf4llm.to_markdown(str(pdf_path))

    def extract_text_by_pages(
        self,
        pdf_path: Path,
    ) -> list[dict[str, Any]]:
        """
        Extrae texto página por página.

        CUÁNDO USAR
        ===========

        Útil para:
        - Papers muy largos (evitar memory issues)
        - Procesamiento paralelo por página
        - Debugging (identificar qué página tiene problemas)

        OUTPUT
        ======

        Lista de diccionarios, cada uno con:
        - "text": Markdown de la página
        - "page": Número de página
        - "metadata": Info adicional

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            Lista de páginas con texto y metadatos
        """
        # page_chunks=True divide el output por página
        pages = pymupdf4llm.to_markdown(
            str(pdf_path),
            page_chunks=True,
        )
        return pages

    # -------------------------------------------------------------------------
    # MÉTODOS DE CHUNKING
    # -------------------------------------------------------------------------

    def create_chunks(
        self,
        text: str,
        paper_id: str,
        metadata: Optional[dict] = None,
    ) -> list[dict[str, Any]]:
        """
        Crea chunks de texto para el vector store.

        ALGORITMO RECURSIVECHARACTERTEXTSPLITTER
        ========================================

        Implementa la lógica de LangChain's RecursiveCharacterTextSplitter:

            1. Intentar split por párrafos ("\\n\\n")
            2. Si chunk > 1000, split por líneas ("\\n")
            3. Si chunk > 1000, split por oraciones (". ")
            4. Si chunk > 1000, split por cláusulas (", ")
            5. Último recurso: split por palabras (" ")

        OVERLAP
        =======

        Después del split, se añade overlap:

            Chunk N:    [..............texto................]
            Chunk N+1:           [overlap|...texto...........]
                                    ↑
                              200 caracteres del chunk anterior

        DETECCIÓN DE SECCIONES
        ======================

        Cada chunk se etiqueta con su sección:
        - abstract, introduction, methods, results, etc.

        Esto permite filtrar por sección en búsquedas.

        Uses RecursiveCharacterTextSplitter logic:
        - 1000 characters per chunk
        - 200 character overlap
        - Hierarchical separators: paragraphs → lines → sentences → words

        Args:
            text: Texto completo a fragmentar
            paper_id: Identificador del paper
            metadata: Metadatos opcionales para incluir en chunks

        Returns:
            Lista de diccionarios de chunks listos para vector store
        """
        metadata = metadata or {}
        chunks = []

        # ---------------------------------------------------------------------
        # PASO 1: SPLIT RECURSIVO
        # ---------------------------------------------------------------------

        # Aplicar split jerárquico usando separadores
        current_chunks = self._recursive_split(
            text,
            self.chunk_separators,
            self.chunk_size,
        )

        # ---------------------------------------------------------------------
        # PASO 2: AÑADIR OVERLAP
        # ---------------------------------------------------------------------

        # Añadir overlap entre chunks consecutivos
        overlapped_chunks = self._add_overlap(current_chunks, self.chunk_overlap)

        # ---------------------------------------------------------------------
        # PASO 3: CREAR REGISTROS DE CHUNKS
        # ---------------------------------------------------------------------

        # Detectar sección y crear diccionario para cada chunk
        for i, chunk_text in enumerate(overlapped_chunks):
            # Detectar sección basándose en contenido
            section = self._detect_section(chunk_text)

            # Construir registro de chunk
            chunk = {
                "paper_id": paper_id,
                "chunk_index": i,
                "text": chunk_text,
                "section": section,
                # Incluir metadatos adicionales (título, año, autores, etc.)
                **metadata,
            }
            chunks.append(chunk)

        return chunks

    def _recursive_split(
        self,
        text: str,
        separators: list[str],
        chunk_size: int,
    ) -> list[str]:
        """
        Divide texto recursivamente usando separadores jerárquicos.

        ALGORITMO
        =========

        El algoritmo intenta mantener unidades semánticas:

            1. Tomar el primer separador (ej: "\\n\\n")
            2. Dividir texto por ese separador
            3. Agrupar partes hasta chunk_size
            4. Si una parte > chunk_size, recursión con siguiente separador

        COMPLEJIDAD
        ===========

            Tiempo: O(n * s) donde n=largo texto, s=número separadores
            Espacio: O(n) para almacenar chunks

        EJEMPLO
        =======

            Texto: "Párrafo 1...\\n\\nPárrafo 2 muy largo...\\n\\nPárrafo 3"
            Separador: "\\n\\n"

            1. Split: ["Párrafo 1...", "Párrafo 2 muy largo...", "Párrafo 3"]
            2. Chunk 1: "Párrafo 1..." (OK, < 1000)
            3. "Párrafo 2 muy largo..." > 1000 → recursión con "\\n"
            4. Chunk 2: parte de párrafo 2
            5. ...

        Mirrors LangChain's RecursiveCharacterTextSplitter:
        paragraphs → lines → sentences → words

        Args:
            text: Texto a dividir
            separators: Lista de separadores en orden de preferencia
            chunk_size: Tamaño máximo de chunk

        Returns:
            Lista de strings (chunks)
        """
        # Caso base: texto vacío
        if not text:
            return []

        # Caso base: texto ya es suficientemente pequeño
        if len(text) <= chunk_size:
            return [text]

        # Intentar cada separador en orden de prioridad
        for sep in separators:
            if sep in text:
                # Dividir por este separador
                parts = text.split(sep)
                chunks = []
                current = ""

                for part in parts:
                    # ¿Añadir esta parte excedería el límite?
                    test = current + sep + part if current else part

                    if len(test) <= chunk_size:
                        # Cabe en el chunk actual
                        current = test
                    else:
                        # No cabe, guardar chunk actual
                        if current:
                            chunks.append(current)

                        # ¿La parte misma es demasiado grande?
                        if len(part) > chunk_size:
                            # Recursión con siguiente separador
                            remaining_seps = separators[separators.index(sep) + 1:]
                            if remaining_seps:
                                chunks.extend(
                                    self._recursive_split(part, remaining_seps, chunk_size)
                                )
                            else:
                                # Sin más separadores, forzar split por tamaño
                                for j in range(0, len(part), chunk_size):
                                    chunks.append(part[j:j + chunk_size])
                            current = ""
                        else:
                            # La parte cabe como nuevo chunk
                            current = part

                # No olvidar el último chunk
                if current:
                    chunks.append(current)

                return chunks

        # Ningún separador encontrado, forzar split por tamaño
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    def _add_overlap(self, chunks: list[str], overlap: int) -> list[str]:
        """
        Añade overlap entre chunks consecutivos.

        PROPÓSITO
        =========

        El overlap asegura que información en boundaries no se pierda:

            Sin overlap:
                Chunk 1: "...attention mechanism is"
                Chunk 2: "very effective for..."

            Con overlap:
                Chunk 1: "...attention mechanism is"
                Chunk 2: "mechanism is very effective for..."
                          ↑ overlap de chunk anterior

        IMPLEMENTACIÓN
        ==============

        Para cada chunk N>0:
            overlap_text = últimos `overlap` caracteres de chunk N-1
            chunk_N = overlap_text + chunk_N

        Args:
            chunks: Lista de chunks originales
            overlap: Número de caracteres de overlap

        Returns:
            Lista de chunks con overlap añadido
        """
        # Casos especiales
        if not chunks or overlap == 0:
            return chunks

        # Primer chunk no tiene overlap
        result = [chunks[0]]

        for i in range(1, len(chunks)):
            # Obtener overlap del chunk anterior
            prev = chunks[i - 1]
            overlap_text = prev[-overlap:] if len(prev) > overlap else prev

            # Añadir overlap al chunk actual
            result.append(overlap_text + chunks[i])

        return result

    def _detect_section(self, text: str) -> str:
        """
        Detecta el tipo de sección desde el contenido del texto.

        PATRONES
        ========

        Busca patrones comunes en papers científicos:

            - "# Abstract" o "Abstract" al inicio
            - "## Introduction" o "1. Introduction"
            - "Methods", "Methodology", "Experimental Setup"
            - "Results", "Experiments"
            - "Discussion", "Conclusion"
            - "References", "Bibliography"

        LIMITACIONES
        ============

        - Solo revisa los primeros 500 caracteres
        - Depende de que el PDF preserve headers
        - Puede fallar en papers con formato inusual

        FALLBACK
        ========

        Si no se detecta sección específica, retorna "body".

        Looks for common scientific paper sections.

        Args:
            text: Texto del chunk

        Returns:
            Nombre de la sección detectada o "body"
        """
        # Revisar solo los primeros 500 caracteres (donde estaría el header)
        text_lower = text.lower()[:500]

        # Patrones de secciones comunes
        # Formato: (regex_pattern, section_name)
        section_patterns = [
            (r"^\s*#*\s*abstract", "abstract"),
            (r"^\s*#*\s*introduction", "introduction"),
            (r"^\s*#*\s*background", "background"),
            (r"^\s*#*\s*related\s+work", "related_work"),
            (r"^\s*#*\s*method", "methods"),         # Matches "method", "methods", "methodology"
            (r"^\s*#*\s*experiment", "experiments"),
            (r"^\s*#*\s*result", "results"),
            (r"^\s*#*\s*discussion", "discussion"),
            (r"^\s*#*\s*conclusion", "conclusion"),
            (r"^\s*#*\s*reference", "references"),
            (r"^\s*#*\s*appendix", "appendix"),
        ]

        # Buscar cada patrón
        for pattern, section in section_patterns:
            if re.search(pattern, text_lower):
                return section

        # Fallback: sección genérica
        return "body"

    # -------------------------------------------------------------------------
    # PIPELINE COMPLETO
    # -------------------------------------------------------------------------

    async def process_pdf(
        self,
        pdf_path: Path,
        paper_id: str,
        use_grobid: bool = True,
    ) -> dict[str, Any]:
        """
        Pipeline completo de procesamiento de PDF.

        PASOS
        =====

        1. Extraer metadatos estructurados con GROBID (si disponible)
        2. Extraer texto markdown con PyMuPDF4LLM
        3. Crear chunks para vector store

        RESULTADO
        =========

        Diccionario con:
        - paper_id: ID del paper
        - pdf_path: Ruta al PDF
        - metadata: PaperMetadata (o None si GROBID falla)
        - text: Texto completo en markdown
        - chunks: Lista de chunks listos para vectorización
        - grobid_used: Si se usó GROBID exitosamente

        TOLERANCIA A FALLOS
        ===================

        Si GROBID no está disponible:
        - metadata será None
        - chunks no tendrán metadatos de GROBID
        - El procesamiento continúa con PyMuPDF4LLM

        1. Extract structured metadata with GROBID (if available)
        2. Extract markdown text with PyMuPDF4LLM
        3. Create chunks for vector store

        Args:
            pdf_path: Ruta al archivo PDF
            paper_id: Identificador del paper
            use_grobid: Si intentar usar GROBID

        Returns:
            Diccionario con metadata, text, y chunks
        """
        # Inicializar resultado
        result = {
            "paper_id": paper_id,
            "pdf_path": str(pdf_path),
            "metadata": None,
            "text": "",
            "chunks": [],
            "grobid_used": False,
        }

        # ---------------------------------------------------------------------
        # PASO 1: EXTRAER METADATOS CON GROBID
        # ---------------------------------------------------------------------

        if use_grobid:
            metadata = await self.extract_metadata_grobid(pdf_path)
            if metadata:
                result["metadata"] = metadata
                result["grobid_used"] = True

        # ---------------------------------------------------------------------
        # PASO 2: EXTRAER TEXTO CON PYMUPDF4LLM
        # ---------------------------------------------------------------------

        text = self.extract_text(pdf_path)
        result["text"] = text

        # ---------------------------------------------------------------------
        # PASO 3: CREAR CHUNKS
        # ---------------------------------------------------------------------

        # Preparar metadatos para incluir en cada chunk
        chunk_metadata = {}
        if result["metadata"]:
            # Si tenemos metadatos de GROBID, incluirlos en chunks
            chunk_metadata = {
                "title": result["metadata"].title,
                "year": result["metadata"].year,
                "authors": [a.name for a in result["metadata"].authors],
                "doi": result["metadata"].doi,
            }

        # Crear chunks con metadatos
        result["chunks"] = self.create_chunks(text, paper_id, chunk_metadata)

        return result


# =============================================================================
# SINGLETON: GET PDF PROCESSOR
# =============================================================================

@lru_cache
def get_pdf_processor() -> PDFProcessor:
    """
    Obtiene instancia singleton del procesador PDF.

    ¿POR QUÉ SINGLETON?
    ===================

    1. CLIENTE HTTP: Reutiliza conexiones HTTP con GROBID
    2. CONFIGURACIÓN: Consistente en toda la aplicación
    3. EFICIENCIA: Evita recrear instancias

    USO
    ===

        processor = get_pdf_processor()
        result = await processor.process_pdf("paper.pdf", "id-123")

    Returns:
        Instancia singleton de PDFProcessor
    """
    settings = get_settings()
    return PDFProcessor(
        grobid_url=settings.grobid_url,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
