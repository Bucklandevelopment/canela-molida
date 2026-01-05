"""
Streamlit Frontend for Scientific Library RAG.

=============================================================================
                        INTERFAZ DE USUARIO STREAMLIT
=============================================================================

Este módulo implementa la interfaz gráfica de usuario para el sistema RAG.
Streamlit permite crear interfaces web interactivas con Python puro,
sin necesidad de HTML/CSS/JavaScript.

ARQUITECTURA FRONTEND-BACKEND:
==============================

┌─────────────────────────────────────────────────────────────────────────┐
│                          STREAMLIT FRONTEND                             │
│                         (localhost:8501)                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        PÁGINAS                                   │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│  │  │  Chat   │ │ Search  │ │ Ingest  │ │ Prizes  │ │  Stats  │   │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │   │
│  │       │           │           │           │           │         │   │
│  └───────┼───────────┼───────────┼───────────┼───────────┼─────────┘   │
│          │           │           │           │           │             │
│  ┌───────┴───────────┴───────────┴───────────┴───────────┴─────────┐   │
│  │                     API REQUEST LAYER                            │   │
│  │                     (httpx Client)                               │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │ HTTP (JSON)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND                                │
│                         (localhost:3690)                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │   /api/rag/*    /api/papers/*    /api/ingest/*    /api/search/* │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

¿QUÉ ES STREAMLIT?
==================

Streamlit es un framework para crear aplicaciones web de datos en Python.
Filosofía: "Write Python scripts, get beautiful web apps."

COMPARACIÓN CON ALTERNATIVAS:
─────────────────────────────
│ Framework  │ Complejidad │ Customización │ Curva    │ Uso típico     │
├────────────┼─────────────┼───────────────┼──────────┼────────────────┤
│ Streamlit  │ Mínima      │ Limitada      │ 1 hora   │ Data apps, ML  │
│ Gradio     │ Mínima      │ Limitada      │ 1 hora   │ ML demos       │
│ Dash       │ Media       │ Alta          │ 1 semana │ Dashboards     │
│ React      │ Alta        │ Total         │ 1 mes    │ Apps complejas │

FLUJO DE EJECUCIÓN DE STREAMLIT:
================================

    1. Usuario visita localhost:8501
           │
           ▼
    2. Streamlit ejecuta app.py COMPLETO
           │
           ▼
    3. Renderiza widgets en el navegador
           │
           ▼
    4. Usuario interactúa (botón, input, etc.)
           │
           ▼
    5. Streamlit RE-EJECUTA app.py COMPLETO
           │
           ▼
    6. Solo widgets modificados se actualizan (diffing)

IMPORTANTE: Cada interacción re-ejecuta TODO el script.
Por eso usamos st.session_state para persistir datos entre re-runs.

SESSION STATE - PERSISTENCIA ENTRE RE-RUNS:
============================================

    # SIN session_state (se pierde en cada re-run):
    counter = 0
    if st.button("Increment"):
        counter += 1  # ¡Siempre vuelve a 0!

    # CON session_state (persiste):
    if "counter" not in st.session_state:
        st.session_state.counter = 0
    if st.button("Increment"):
        st.session_state.counter += 1  # ¡Se acumula!

PÁGINAS DE LA APLICACIÓN:
=========================

1. CHAT (render_chat)
   - Interfaz conversacional tipo ChatGPT
   - Usa st.chat_message para burbujas de chat
   - Llama a /api/rag/query para respuestas RAG
   - Muestra sources en expanders

2. SEARCH (render_search)
   - 3 pestañas: Papers indexados, OpenAlex, arXiv
   - Búsqueda en vectorstore local
   - Descubrimiento de papers externos
   - Botones para ingestar papers encontrados

3. INGEST (render_ingest)
   - Upload de PDFs locales
   - Ingestión por ID de arXiv (individual o batch)
   - Barra de progreso para batch operations

4. PRIZES (render_prizes)
   - Explorer de premios científicos
   - Nobel (API oficial), Fields, Turing (Wikidata)
   - Búsqueda por Q-ID genérico

5. STATS (render_stats)
   - Estadísticas del sistema
   - Métricas de vectorstore y cache

Ejecución:
    streamlit run frontend/app.py

    # Con configuración:
    streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0
"""

# =============================================================================
# IMPORTS
# =============================================================================

# ---------------------------------------------------------------------------
# Streamlit - Framework de UI
# ---------------------------------------------------------------------------
import streamlit as st  # El framework principal, importado como 'st' por convención

# ---------------------------------------------------------------------------
# HTTP Client - Comunicación con el backend
# ---------------------------------------------------------------------------
import httpx  # Cliente HTTP moderno, alternativa a requests con async support

# ---------------------------------------------------------------------------
# Async Support - Para operaciones asíncronas
# ---------------------------------------------------------------------------
import asyncio  # Event loop para async (no usado actualmente, reservado para streaming)

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
from datetime import datetime  # Para timestamps (no usado actualmente)


# =============================================================================
# CONFIGURACIÓN GLOBAL
# =============================================================================

# URL base del backend FastAPI
# En desarrollo: localhost:3690
# En Docker: http://api:3690 (nombre del servicio)
# Configuración externalizable vía st.secrets o variables de entorno
API_URL = "http://localhost:3690"


# =============================================================================
# SESSION STATE - Estado persistente entre re-runs
# =============================================================================

def init_session_state():
    """
    Inicializa las variables del session_state.

    SESSION STATE EXPLICADO:
    ========================

    Streamlit re-ejecuta TODO el script en cada interacción del usuario.
    Sin session_state, todas las variables se reinicializarían.

    session_state es un diccionario que persiste entre re-runs:

        ┌─────────────────────────────────────────────────────────────┐
        │                     STREAMLIT PROCESS                        │
        │  ┌─────────────────────────────────────────────────────────┐    │
        │  │               SESSION STATE (dict)                   │    │
        │  │  {                                                   │    │
        │  │      "messages": [...],  # Historial del chat       │    │
        │  │      "papers": [...]      # Papers cargados          │    │
        │  │  }                                                   │    │
        │  └─────────────────────────────────────────────────────┘    │
        │                          │                                   │
        │     ┌────────────────────┼────────────────────┐             │
        │     │                    │                    │             │
        │     ▼                    ▼                    ▼             │
        │  [Re-run 1]         [Re-run 2]           [Re-run 3]        │
        │  (click btn)        (type text)          (select)          │
        └─────────────────────────────────────────────────────────────┘

    PATRÓN DE INICIALIZACIÓN:
    =========================

    Siempre verificar si la key existe antes de inicializar:

        if "key" not in st.session_state:
            st.session_state.key = default_value

    Esto evita reinicializar en cada re-run.

    VARIABLES DE ESTADO:
    ====================

    messages: list[dict]
        - Historial de mensajes del chat
        - Formato: [{"role": "user"|"assistant", "content": str, "sources": [...]}]
        - Persiste toda la conversación durante la sesión

    papers: list[dict]
        - Papers actualmente cargados (para futuras features)
        - Reservado para cachear resultados de búsqueda

    first_visit: bool
        - True si es la primera visita del usuario
        - Se usa para mostrar tutorial inicial

    tutorial_dismissed: bool
        - True si el usuario ha cerrado el tutorial
    """
    # Inicializar historial de chat si no existe
    # Cada mensaje es un dict con role (user/assistant) y content
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Inicializar lista de papers (para caché de búsquedas)
    if "papers" not in st.session_state:
        st.session_state.papers = []

    # Tutorial: primera visita
    if "first_visit" not in st.session_state:
        st.session_state.first_visit = True

    # Tutorial: si el usuario lo ha cerrado
    if "tutorial_dismissed" not in st.session_state:
        st.session_state.tutorial_dismissed = False


# =============================================================================
# API CLIENT - Comunicación con el backend
# =============================================================================

def api_request(endpoint: str, method: str = "GET", **kwargs) -> dict:
    """
    Realiza peticiones HTTP síncronas al backend FastAPI.

    HTTPX vs REQUESTS:
    ==================

    │ Feature          │ httpx           │ requests       │
    ├──────────────────┼─────────────────┼────────────────┤
    │ Async support    │ ✓ (nativo)      │ ✗              │
    │ HTTP/2           │ ✓               │ ✗              │
    │ Timeouts         │ Granulares      │ Básicos        │
    │ Connection pool  │ Mejor           │ Bueno          │
    │ API              │ Similar         │ Estándar       │

    Usamos httpx porque:
    1. Soporte futuro para streaming async
    2. Mejor manejo de timeouts (crítico para RAG lento)
    3. API compatible con requests (fácil migración)

    CONTEXT MANAGER (with):
    =======================

    with httpx.Client(...) as client:
        # El cliente se crea aquí
        response = client.get(...)
        # El cliente se cierra automáticamente al salir

    Esto asegura que las conexiones se cierren correctamente,
    evitando memory leaks y conexiones huérfanas.

    TIMEOUT:
    ========

    timeout=120.0 (2 minutos) es alto porque:
    - RAG query puede tardar 30-60s (embedding + retrieval + LLM)
    - Ingestión de PDF grande puede tardar 1-2 minutos
    - Mejor timeout largo que requests fallidos

    Args:
        endpoint: Ruta del endpoint (ej: "/api/rag/query")
        method: Método HTTP ("GET" o "POST")
        **kwargs: Argumentos adicionales:
            - params: dict para query parameters (GET)
            - json: dict para body JSON (POST)
            - files: dict para multipart/form-data (POST)

    Returns:
        dict: Respuesta JSON parseada

    Raises:
        httpx.HTTPStatusError: Si el servidor retorna 4xx/5xx
        httpx.TimeoutException: Si se excede el timeout
        httpx.ConnectError: Si no puede conectar al backend

    Example:
        # GET con parámetros
        result = api_request("/search/papers", params={"query": "AI"})

        # POST con JSON
        result = api_request("/rag/query", method="POST", json={"question": "..."})
    """
    # Crear cliente HTTP con context manager para cleanup automático
    with httpx.Client(base_url=API_URL, timeout=120.0) as client:
        if method == "GET":
            # GET: parámetros van en la URL (?key=value&...)
            response = client.get(endpoint, params=kwargs.get("params"))
        elif method == "POST":
            # POST: datos van en el body (JSON o multipart)
            response = client.post(
                endpoint,
                json=kwargs.get("json"),    # Body JSON (application/json)
                files=kwargs.get("files"),   # Archivos (multipart/form-data)
            )
        else:
            raise ValueError(f"Unsupported method: {method}")

        # raise_for_status() lanza excepción si status >= 400
        # Esto permite manejar errores con try/except en el caller
        response.raise_for_status()

        # Parsear JSON y retornar como dict
        return response.json()


# =============================================================================
# TUTORIAL Y AYUDA - Guías para usuarios nuevos
# =============================================================================

def get_indexed_chunks_count() -> int:
    """
    Obtiene el número de chunks indexados en el sistema.
    Retorna 0 si hay error de conexión.
    """
    try:
        stats = api_request("/stats")
        return stats.get("vectorstore", {}).get("chunks_count", 0)
    except Exception:
        return 0


def show_welcome_tutorial():
    """
    Muestra el tutorial de bienvenida para usuarios nuevos.
    Solo se muestra una vez por sesión.
    """
    if st.session_state.first_visit and not st.session_state.tutorial_dismissed:
        st.session_state.first_visit = False

        # Toast de bienvenida
        st.toast("👋 ¡Bienvenido a Scientific Library RAG!", icon="📚")

        # Verificar si hay papers
        chunks = get_indexed_chunks_count()
        if chunks == 0:
            st.toast("📥 Primero ve a 'Ingest' para añadir papers", icon="💡")


def show_empty_library_warning():
    """
    Muestra un banner de advertencia si la biblioteca está vacía.
    """
    chunks = get_indexed_chunks_count()
    if chunks == 0:
        st.warning(
            "**📚 Tu biblioteca está vacía.** "
            "Ve a la sección **'Ingest'** para añadir papers antes de hacer preguntas. "
            "Puedes subir PDFs locales o descargar papers de arXiv."
        )
        return True
    return False


def show_page_tip(page: str):
    """
    Muestra un toast con información sobre la página actual.
    Solo se muestra una vez por página por sesión.
    """
    tip_key = f"tip_shown_{page}"
    if tip_key not in st.session_state:
        st.session_state[tip_key] = True

        tips = {
            "Chat": "💬 Haz preguntas sobre los papers que has indexado",
            "Search": "🔍 Busca papers en tu biblioteca local o en OpenAlex/arXiv",
            "Ingest": "📥 Añade papers: sube PDFs o descarga de arXiv",
            "Prizes": "🏆 Explora premios científicos: Nobel, Fields, Turing...",
            "Stats": "📊 Ve estadísticas de tu biblioteca y sistema",
        }

        if page in tips:
            st.toast(tips[page], icon="💡")


# =============================================================================
# GROBID STATUS - Verificación del servicio GROBID
# =============================================================================

GROBID_URL = "http://localhost:8070"


def check_grobid_status() -> bool:
    """
    Verifica si GROBID está disponible y listo.
    Retorna True si responde al endpoint /api/isalive.
    """
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{GROBID_URL}/api/isalive")
            return response.status_code == 200
    except Exception:
        return False


def render_grobid_status_widget(widget_key: str = "default"):
    """
    Renderiza un widget que muestra el estado de GROBID.
    Si no está listo, muestra instrucciones y un botón para verificar.

    Args:
        widget_key: Key único para evitar conflictos entre widgets

    Returns:
        bool: True si GROBID está disponible, False si no
    """
    # Inicializar estado de GROBID en session_state
    if "grobid_status" not in st.session_state:
        st.session_state.grobid_status = None

    # Verificar estado actual
    is_available = check_grobid_status()
    st.session_state.grobid_status = is_available

    # Crear contenedor para el widget
    status_container = st.container()

    with status_container:
        if is_available:
            st.success("✅ **GROBID listo** - Extracción de metadatos habilitada")
            return True
        else:
            # GROBID no disponible - mostrar opciones
            st.warning(
                "⏳ **GROBID no disponible** - El servicio no está corriendo o aún está iniciando.\n\n"
                "**Opciones:**\n"
                "1. Inicia GROBID: `make grobid-start` (tarda ~60s en estar listo)\n"
                "2. Desmarca la opción 'Use GROBID' para procesar sin metadatos avanzados"
            )

            # Botón para verificar manualmente
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("🔄 Verificar", key=f"check_grobid_{widget_key}"):
                    is_available = check_grobid_status()
                    if is_available:
                        st.toast("✅ GROBID está listo!", icon="✅")
                        st.rerun()
                    else:
                        st.toast("⏳ GROBID aún no está listo", icon="⏳")

            with col2:
                st.caption("GROBID tarda ~60 segundos en iniciar después de `make grobid-start`")

            return False


# =============================================================================
# PÁGINA: CHAT - Interfaz conversacional RAG
# =============================================================================

def render_chat():
    """
    Renderiza la interfaz de chat para consultas RAG.

    DISEÑO DE CHAT EN STREAMLIT:
    ============================

    Streamlit 1.22+ introdujo componentes nativos de chat:

    st.chat_message("user")     → Burbuja estilo usuario (derecha, azul)
    st.chat_message("assistant") → Burbuja estilo asistente (izquierda, gris)
    st.chat_input()             → Input fijo en la parte inferior

    FLUJO DE LA CONVERSACIÓN:
    =========================

        Usuario escribe pregunta
               │
               ▼
        ┌──────────────────┐
        │ Guardar en       │
        │ session_state    │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ Mostrar burbuja  │
        │ de usuario       │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ POST /rag/query  │  ← Llamada al backend
        │ con spinner      │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ Mostrar respuesta│
        │ + métricas       │
        │ + sources        │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ Guardar respuesta│
        │ en session_state │
        └──────────────────┘

    WALRUS OPERATOR (:=):
    =====================

    if prompt := st.chat_input(...):

    Es equivalente a:
        prompt = st.chat_input(...)
        if prompt:

    Pero más conciso. Asigna Y evalúa en una línea.
    Introducido en Python 3.8 (PEP 572).
    """
    # Título de la sección
    st.header("Ask the Library")

    # Mostrar warning si no hay papers indexados
    if show_empty_library_warning():
        st.info(
            "**💡 Consejo:** Prueba a descargar el paper de Transformers: "
            "ve a **Ingest → From arXiv** e introduce el ID `1706.03762`"
        )

    # =========================================================================
    # RENDERIZAR HISTORIAL DE MENSAJES
    # =========================================================================
    # Iteramos sobre todos los mensajes guardados en session_state
    # Esto reconstruye la conversación visual en cada re-run
    for message in st.session_state.messages:
        # st.chat_message crea un contenedor con avatar y estilo apropiado
        # role="user" → avatar de persona, alineado a la derecha
        # role="assistant" → avatar de robot, alineado a la izquierda
        with st.chat_message(message["role"]):
            # Renderizar contenido como Markdown (soporta formato)
            st.markdown(message["content"])

            # Para mensajes del asistente, mostrar sources en expander
            # Esto permite ver de qué papers vino la información
            if message["role"] == "assistant" and "sources" in message:
                with st.expander("Sources"):
                    for source in message["sources"]:
                        st.markdown(
                            f"**{source['title']}** ({source.get('year', 'N/A')})\n"
                            f"Score: {source['score']:.3f}"
                        )

    # =========================================================================
    # INPUT DE CHAT Y PROCESAMIENTO
    # =========================================================================
    # st.chat_input() renderiza un input fijo en la parte inferior
    # Retorna None si está vacío, el texto si el usuario presiona Enter

    if prompt := st.chat_input("Ask a question about your papers..."):
        # 1. Guardar mensaje del usuario en el historial
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 2. Mostrar burbuja del usuario inmediatamente
        with st.chat_message("user"):
            st.markdown(prompt)

        # 3. Obtener respuesta RAG del backend
        with st.chat_message("assistant"):
            # st.spinner muestra indicador de carga mientras procesa
            with st.spinner("Thinking..."):
                try:
                    # Llamar al endpoint RAG con la pregunta
                    response = api_request(
                        "/rag/query",
                        method="POST",
                        json={
                            "question": prompt,  # La pregunta del usuario
                            "top_k": 10,          # Recuperar 10 chunks relevantes
                            "include_sources": True,  # Incluir metadatos de sources
                        },
                    )

                    # Extraer y mostrar la respuesta generada
                    answer = response["answer"]
                    st.markdown(answer)

                    # Mostrar métricas de performance en 3 columnas
                    # Esto ayuda a entender el rendimiento del sistema
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Retrieval", f"{response['retrieval_time_ms']:.0f}ms")
                    col2.metric("Generation", f"{response['generation_time_ms']:.0f}ms")
                    col3.metric("Cache Hit", "Yes" if response["used_cache"] else "No")

                    # Preparar sources para guardar en session_state
                    # Extraemos solo los campos necesarios para display
                    sources = [
                        {
                            "title": c["title"],
                            "year": c.get("year"),
                            "score": c["score"],
                        }
                        for c in response.get("contexts", [])
                    ]

                    # Guardar respuesta en historial
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                    })

                except Exception as e:
                    # Mostrar error al usuario
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)

                    # Guardar error en historial para contexto
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                    })


# =============================================================================
# PÁGINA: SEARCH - Búsqueda de papers
# =============================================================================

def render_search():
    """
    Renderiza la interfaz de búsqueda de papers.

    PESTAÑAS DE BÚSQUEDA:
    =====================

    ┌─────────────────────────────────────────────────────────────────────┐
    │  [Indexed Papers]  [OpenAlex]  [arXiv]                              │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │  Indexed Papers:                                                    │
    │    - Búsqueda semántica en vectorstore local                       │
    │    - Papers que ya has descargado e indexado                        │
    │    - Filtros por año                                                │
    │                                                                     │
    │  OpenAlex:                                                          │
    │    - 240M+ papers de todas las disciplinas                          │
    │    - Metadatos ricos, abstracts, citaciones                         │
    │    - Filtro Open Access                                             │
    │                                                                     │
    │  arXiv:                                                             │
    │    - 2.5M+ preprints de física, CS, matemáticas                     │
    │    - PDFs gratuitos                                                 │
    │    - Botón para ingestar directamente                               │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    KEY EN WIDGETS:
    ================

    Cada widget necesita un `key` único para evitar conflictos:

        st.text_input(..., key="search_indexed")
        st.text_input(..., key="search_openalex")

    Si dos widgets tienen el mismo key, Streamlit lanza error.
    El key también permite acceder al valor: st.session_state.search_indexed
    """
    st.header("Search Papers")

    # =========================================================================
    # SISTEMA DE PESTAÑAS
    # =========================================================================
    # st.tabs crea pestañas navegables sin recarga de página
    # Retorna contextos que usamos con 'with'
    tab1, tab2, tab3 = st.tabs(["Indexed Papers", "OpenAlex", "arXiv"])

    # =========================================================================
    # PESTAÑA 1: BÚSQUEDA EN PAPERS INDEXADOS (LOCAL)
    # =========================================================================
    with tab1:
        # Input de búsqueda semántica
        query = st.text_input("Search your indexed papers", key="search_indexed")

        # Filtros de año en 2 columnas
        col1, col2 = st.columns(2)
        year_min = col1.number_input("Year from", value=None, key="year_min_idx")
        year_max = col2.number_input("Year to", value=None, key="year_max_idx")

        # Botón de búsqueda
        if st.button("Search", key="btn_search_indexed"):
            with st.spinner("Searching..."):
                try:
                    # Llamar al endpoint de búsqueda local
                    results = api_request(
                        "/search/papers",
                        params={
                            "query": query,     # Texto para búsqueda semántica
                            "top_k": 20,        # Máximo 20 resultados
                            "year_min": year_min,
                            "year_max": year_max,
                        },
                    )

                    # Mostrar resultados
                    st.subheader(f"Found {results['count']} results")
                    for r in results["results"]:
                        # Cada resultado en un expander colapsable
                        with st.expander(f"{r['title']} ({r.get('year', 'N/A')})"):
                            st.markdown(f"**Score:** {r['score']:.3f}")
                            st.markdown(f"**Section:** {r.get('section', 'N/A')}")
                            # Mostrar preview del texto (primeros 500 chars)
                            st.text(r["text"][:500] + "...")
                except Exception as e:
                    st.error(f"Search failed: {e}")

    # =========================================================================
    # PESTAÑA 2: BÚSQUEDA EN OPENALEX (EXTERNO)
    # =========================================================================
    with tab2:
        query = st.text_input("Search OpenAlex (240M+ papers)", key="search_openalex")

        # Controles de búsqueda
        col1, col2 = st.columns(2)
        limit = col1.slider("Results", 10, 100, 25, key="limit_oa")
        oa_only = col2.checkbox("Open Access only", key="oa_only")

        if st.button("Search", key="btn_search_oa"):
            with st.spinner("Searching OpenAlex..."):
                try:
                    results = api_request(
                        "/papers/search/openalex",
                        params={
                            "query": query,
                            "limit": limit,
                            "open_access": oa_only,
                        },
                    )

                    # Mostrar cada paper encontrado
                    for paper in results:
                        with st.expander(f"{paper['title']} ({paper.get('year', 'N/A')})"):
                            # Mostrar primeros 3 autores
                            authors = ", ".join(a["name"] for a in paper.get("authors", [])[:3])
                            st.markdown(f"**Authors:** {authors}")
                            st.markdown(f"**DOI:** {paper.get('doi', 'N/A')}")
                            st.markdown(f"**Open Access:** {'Yes' if paper.get('is_open_access') else 'No'}")
                            if paper.get("abstract"):
                                st.markdown(f"**Abstract:** {paper['abstract'][:300]}...")
                except Exception as e:
                    st.error(f"Search failed: {e}")

    # =========================================================================
    # PESTAÑA 3: BÚSQUEDA EN ARXIV (EXTERNO + INGEST)
    # =========================================================================
    with tab3:
        query = st.text_input("Search arXiv (2.5M+ papers)", key="search_arxiv")

        # Selector de categoría arXiv
        # Las categorías siguen la taxonomía oficial de arXiv
        category = st.selectbox(
            "Category (optional)",
            [None, "cs.AI", "cs.LG", "cs.CL", "physics.quant-ph", "math.CO", "stat.ML"],
            key="arxiv_cat",
        )

        if st.button("Search", key="btn_search_arxiv"):
            with st.spinner("Searching arXiv..."):
                try:
                    params = {"query": query, "max_results": 50}
                    if category:
                        params["category"] = category

                    results = api_request("/papers/search/arxiv", params=params)

                    for paper in results:
                        with st.expander(f"{paper['title']} ({paper.get('year', 'N/A')})"):
                            authors = ", ".join(a["name"] for a in paper.get("authors", [])[:3])
                            st.markdown(f"**Authors:** {authors}")
                            st.markdown(f"**arXiv ID:** {paper.get('arxiv_id')}")
                            st.markdown(f"**Categories:** {', '.join(paper.get('arxiv_categories', []))}")
                            if paper.get("abstract"):
                                st.markdown(f"**Abstract:** {paper['abstract'][:300]}...")

                            # Botón para ingestar este paper directamente
                            # Cada botón necesita key único basado en arxiv_id
                            if st.button(f"Ingest {paper['arxiv_id']}", key=f"ingest_{paper['arxiv_id']}"):
                                with st.spinner("Ingesting..."):
                                    try:
                                        result = api_request(
                                            f"/ingest/arxiv/{paper['arxiv_id']}",
                                            method="POST",
                                            json={},
                                        )
                                        st.success(f"Ingested {result['chunks_count']} chunks")
                                    except Exception as e:
                                        st.error(f"Ingestion failed: {e}")
                except Exception as e:
                    st.error(f"Search failed: {e}")


# =============================================================================
# PÁGINA: INGEST - Ingestión de papers al sistema
# =============================================================================

def render_ingest():
    """
    Renderiza la interfaz de ingestión de papers.

    FLUJO DE INGESTIÓN:
    ===================

    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
    │   PDF Upload    │     │  Descarga PDF   │     │   Extracción    │
    │   o arXiv ID    │────▶│   (si arXiv)    │────▶│   de texto      │
    └─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                              │
    ┌─────────────────┐     ┌─────────────────┐              │
    │   Indexar en    │◀────│   Chunking +    │◀─────────────┘
    │   LanceDB       │     │   Embeddings    │
    └─────────────────┘     └─────────────────┘

    MÉTODOS DE INGESTIÓN:
    =====================

    1. Upload PDF:
       - Usuario sube archivo desde su computadora
       - Se envía como multipart/form-data
       - GROBID extrae metadatos (título, autores, abstract)

    2. From arXiv:
       - Usuario proporciona IDs de arXiv
       - Backend descarga PDF automáticamente
       - Soporta batch (múltiples IDs)
       - Barra de progreso para batch

    FILE UPLOADER:
    ==============

    st.file_uploader retorna un objeto UploadedFile con:
    - .name: Nombre del archivo
    - .getvalue(): Bytes del archivo
    - .read(): Similar a file.read()
    - .type: MIME type

    MULTIPART FORM DATA:
    ====================

    Para enviar archivos por HTTP, usamos multipart/form-data:

        files = {
            "file": (filename, bytes, content_type)
        }
        client.post(..., files=files, data={...})

    Esto es diferente a JSON body - permite enviar binarios.
    """
    st.header("Ingest Papers")

    # Guía rápida para usuarios nuevos
    with st.expander("📖 Guía rápida", expanded=False):
        st.markdown("""
        **¿Cómo funciona?**

        1. **Sube un PDF** o **introduce un ID de arXiv**
        2. El sistema extrae el texto del documento
        3. Lo divide en fragmentos (chunks) de ~1000 caracteres
        4. Genera embeddings vectoriales con BGE-M3
        5. Los indexa en la base de datos para búsqueda semántica

        **Ejemplo de ID de arXiv:** `1706.03762` (Paper de Transformers)

        **GROBID (opcional):** Si tienes GROBID corriendo (`make grobid-start`),
        se extraerán metadatos más ricos (título, autores, abstract por separado).
        """)

    # Dos métodos de ingestión en pestañas separadas
    tab1, tab2 = st.tabs(["Upload PDF", "From arXiv"])

    # =========================================================================
    # PESTAÑA 1: UPLOAD DE PDF LOCAL
    # =========================================================================
    with tab1:
        # Widget de upload de archivos
        # type=["pdf"] restringe a solo PDFs
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

        # ID opcional (se genera desde filename si no se proporciona)
        paper_id = st.text_input("Paper ID (optional, auto-generated from filename)")

        # Checkbox para GROBID (extracción de metadatos avanzada)
        use_grobid = st.checkbox("Use GROBID for metadata", value=True)

        # Mostrar estado de GROBID si está habilitado
        grobid_ready = True
        if use_grobid:
            grobid_ready = render_grobid_status_widget("pdf_upload")

        # Procesar cuando hay archivo Y se presiona el botón
        if st.button("Process PDF", disabled=(use_grobid and not grobid_ready)) and uploaded_file:
            with st.spinner("Processing PDF..."):
                try:
                    # Preparar archivo para multipart upload
                    # Formato: {"field_name": (filename, bytes, content_type)}
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}

                    # Para multipart, usamos httpx directamente
                    # (api_request no soporta files + data combinados)
                    with httpx.Client(base_url=API_URL, timeout=120.0) as client:
                        response = client.post(
                            "/ingest/pdf",
                            files=files,
                            data={
                                "paper_id": paper_id or "",
                                "use_grobid": str(use_grobid).lower(),  # "true"/"false"
                            },
                        )
                        response.raise_for_status()
                        result = response.json()

                    # Mostrar resultado exitoso
                    st.success(f"Ingested {result['chunks_count']} chunks")
                    st.json(result)  # JSON formateado para debug
                except Exception as e:
                    st.error(f"Processing failed: {e}")

    # =========================================================================
    # PESTAÑA 2: INGESTIÓN DESDE ARXIV (CON PREVIEW)
    # =========================================================================
    with tab2:
        st.markdown("**Introduce IDs de arXiv para ver información antes de ingestar**")

        # Text area para múltiples IDs (uno por línea)
        arxiv_ids = st.text_area(
            "arXiv IDs (one per line)",
            placeholder="1706.03762\n2301.00001\n...",
            help="Introduce uno o más IDs de arXiv. Ejemplo: 1706.03762 (Transformers)",
        )

        # Inicializar estado para papers previsualizados
        if "arxiv_previews" not in st.session_state:
            st.session_state.arxiv_previews = []
        if "arxiv_selected" not in st.session_state:
            st.session_state.arxiv_selected = set()

        # Botón para previsualizar
        col_preview, col_clear = st.columns([1, 1])
        with col_preview:
            if st.button("🔍 Preview Papers", key="btn_preview_arxiv"):
                ids = [id.strip() for id in arxiv_ids.split("\n") if id.strip()]
                if ids:
                    st.session_state.arxiv_previews = []
                    st.session_state.arxiv_selected = set()

                    progress = st.progress(0)
                    for i, arxiv_id in enumerate(ids):
                        try:
                            # Obtener metadatos del paper
                            paper = api_request(f"/papers/by-arxiv/{arxiv_id}")
                            st.session_state.arxiv_previews.append(paper)
                            st.session_state.arxiv_selected.add(arxiv_id)
                        except Exception as e:
                            st.session_state.arxiv_previews.append({
                                "arxiv_id": arxiv_id,
                                "error": str(e)
                            })
                        progress.progress((i + 1) / len(ids))
                    st.rerun()

        with col_clear:
            if st.button("🗑️ Clear Preview", key="btn_clear_preview"):
                st.session_state.arxiv_previews = []
                st.session_state.arxiv_selected = set()
                st.rerun()

        # Mostrar papers previsualizados
        if st.session_state.arxiv_previews:
            st.markdown("---")
            st.subheader(f"📄 Papers encontrados ({len(st.session_state.arxiv_previews)})")

            for paper in st.session_state.arxiv_previews:
                arxiv_id = paper.get("arxiv_id", "unknown")

                if "error" in paper:
                    st.error(f"❌ **{arxiv_id}**: {paper['error']}")
                    continue

                # Checkbox para seleccionar
                is_selected = st.checkbox(
                    f"**{paper.get('title', 'Sin título')}**",
                    value=arxiv_id in st.session_state.arxiv_selected,
                    key=f"select_{arxiv_id}"
                )

                # Actualizar selección
                if is_selected:
                    st.session_state.arxiv_selected.add(arxiv_id)
                else:
                    st.session_state.arxiv_selected.discard(arxiv_id)

                # Mostrar detalles en expander
                with st.expander(f"📋 Detalles: {arxiv_id}", expanded=False):
                    # Autores
                    authors = paper.get("authors", [])
                    if authors:
                        author_names = ", ".join(a.get("name", "") for a in authors[:5])
                        if len(authors) > 5:
                            author_names += f" (+{len(authors) - 5} more)"
                        st.markdown(f"**Autores:** {author_names}")

                    # Fecha y categorías
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Publicado:** {paper.get('year', 'N/A')}")
                    with col2:
                        cats = paper.get("arxiv_categories", [])
                        st.markdown(f"**Categorías:** {', '.join(cats[:3])}")

                    # Abstract
                    abstract = paper.get("abstract", "")
                    if abstract:
                        st.markdown("**Abstract:**")
                        st.caption(abstract[:500] + ("..." if len(abstract) > 500 else ""))

                    # Link al PDF
                    pdf_url = paper.get("pdf_url", "")
                    if pdf_url:
                        st.markdown(f"[📥 Ver PDF en arXiv]({pdf_url})")

            # Sección de ingestión
            st.markdown("---")
            selected_count = len(st.session_state.arxiv_selected)
            st.markdown(f"**Papers seleccionados:** {selected_count}")

            # GROBID checkbox
            use_grobid_arxiv = st.checkbox(
                "Use GROBID for metadata",
                value=True,
                key="grobid_arxiv"
            )

            # Mostrar estado de GROBID si está habilitado
            grobid_ready_arxiv = True
            if use_grobid_arxiv:
                grobid_ready_arxiv = render_grobid_status_widget("arxiv_ingest")

            # Botón de ingestión
            can_ingest = selected_count > 0 and (not use_grobid_arxiv or grobid_ready_arxiv)

            if st.button(
                f"📥 Ingest {selected_count} Selected Papers",
                disabled=not can_ingest,
                key="btn_ingest_selected"
            ):
                ids = list(st.session_state.arxiv_selected)
                progress = st.progress(0)
                results = []

                for i, arxiv_id in enumerate(ids):
                    with st.spinner(f"Processing {arxiv_id}..."):
                        try:
                            result = api_request(
                                f"/ingest/arxiv/{arxiv_id}",
                                method="POST",
                                json={"use_grobid": use_grobid_arxiv},
                            )
                            results.append({"arxiv_id": arxiv_id, "status": "success", **result})
                        except Exception as e:
                            results.append({"arxiv_id": arxiv_id, "status": "error", "error": str(e)})

                    progress.progress((i + 1) / len(ids))

                # Mostrar resumen
                success = sum(1 for r in results if r["status"] == "success")
                st.success(f"✅ Ingested {success}/{len(ids)} papers")

                for r in results:
                    if r["status"] == "success":
                        st.markdown(f"- ✅ {r['arxiv_id']}: {r.get('chunks_count', 0)} chunks")
                    else:
                        st.markdown(f"- ❌ {r['arxiv_id']}: {r.get('error')}")

                # Limpiar selección después de ingestar
                st.session_state.arxiv_previews = []
                st.session_state.arxiv_selected = set()

        else:
            # Modo rápido sin preview (para usuarios avanzados)
            with st.expander("⚡ Modo rápido (sin preview)", expanded=False):
                st.caption("Ingesta directa sin ver la información primero")

                use_grobid_quick = st.checkbox(
                    "Use GROBID",
                    value=True,
                    key="grobid_quick"
                )

                grobid_ready_quick = True
                if use_grobid_quick:
                    grobid_ready_quick = render_grobid_status_widget("arxiv_quick")

                if st.button(
                    "⚡ Ingest Directly",
                    disabled=(use_grobid_quick and not grobid_ready_quick),
                    key="btn_quick_ingest"
                ):
                    ids = [id.strip() for id in arxiv_ids.split("\n") if id.strip()]
                    if ids:
                        progress = st.progress(0)
                        results = []

                        for i, arxiv_id in enumerate(ids):
                            with st.spinner(f"Processing {arxiv_id}..."):
                                try:
                                    result = api_request(
                                        f"/ingest/arxiv/{arxiv_id}",
                                        method="POST",
                                        json={"use_grobid": use_grobid_quick},
                                    )
                                    results.append({"arxiv_id": arxiv_id, "status": "success", **result})
                                except Exception as e:
                                    results.append({"arxiv_id": arxiv_id, "status": "error", "error": str(e)})
                            progress.progress((i + 1) / len(ids))

                        success = sum(1 for r in results if r["status"] == "success")
                        st.success(f"Processed {success}/{len(ids)} papers")

                        for r in results:
                            if r["status"] == "success":
                                st.markdown(f"- ✅ {r['arxiv_id']}: {r.get('chunks_count', 0)} chunks")
                            else:
                                st.markdown(f"- ❌ {r['arxiv_id']}: {r.get('error')}")


# =============================================================================
# PÁGINA: PRIZES - Explorador de premios científicos
# =============================================================================

def render_prizes():
    """
    Renderiza el explorador de premios científicos.

    PREMIOS DISPONIBLES:
    ====================

    ┌─────────────────────────────────────────────────────────────────────┐
    │                    FUENTES DE DATOS                                 │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │  Nobel Prize (API oficial):                                         │
    │    - Datos desde 1901                                               │
    │    - 6 categorías: Physics, Chemistry, Medicine,                    │
    │                    Literature, Peace, Economics                     │
    │    - Incluye motivaciones oficiales                                 │
    │                                                                     │
    │  Fields Medal (Wikidata SPARQL):                                    │
    │    - "Nobel de las matemáticas"                                     │
    │    - Desde 1936, cada 4 años                                        │
    │    - Máximo 40 años de edad                                         │
    │                                                                     │
    │  Turing Award (Wikidata SPARQL):                                    │
    │    - "Nobel de la computación"                                      │
    │    - Desde 1966                                                     │
    │    - Otorgado por ACM                                               │
    │                                                                     │
    │  Otros (Wikidata por Q-ID):                                         │
    │    - Abel Prize, Wolf Prize, Breakthrough Prize...                  │
    │    - Cualquier premio con entidad en Wikidata                       │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    WIKIDATA Q-IDs:
    ===============

    Wikidata asigna identificadores únicos (Q-IDs) a entidades:
    - Q28835   → Fields Medal
    - Q185667  → Turing Award
    - Q160042  → Abel Prize

    Podemos consultar cualquier premio conociendo su Q-ID.
    Búsqueda de Q-IDs: https://www.wikidata.org/
    """
    st.header("Scientific Prizes")

    # 4 pestañas para diferentes premios
    tab1, tab2, tab3, tab4 = st.tabs(["Nobel Prize", "Fields Medal", "Turing Award", "Other Prizes"])

    # =========================================================================
    # PESTAÑA 1: PREMIO NOBEL (API OFICIAL)
    # =========================================================================
    with tab1:
        st.subheader("Nobel Prize Laureates")

        # Filtros en 2 columnas
        col1, col2 = st.columns(2)

        # Selector de categoría Nobel
        category = col1.selectbox(
            "Category",
            [None, "physics", "chemistry", "medicine", "literature", "peace", "economics"],
            key="nobel_cat",
        )

        # Filtro por año (Nobel empezó en 1901)
        year = col2.number_input("Year", value=None, min_value=1901, max_value=datetime.now().year, key="nobel_year")

        if st.button("Search Nobel Laureates"):
            with st.spinner("Fetching from Nobel API..."):
                try:
                    # Construir parámetros solo si tienen valor
                    params = {}
                    if category:
                        params["category"] = category
                    if year:
                        params["year"] = int(year)

                    results = api_request("/search/nobel", params=params)

                    st.subheader(f"Found {results['count']} laureates")

                    # Mostrar cada laureado
                    for l in results["laureates"]:
                        # Construir string de premios (puede tener múltiples)
                        prizes = ", ".join(
                            f"{p['category']} ({p['year']})"
                            for p in l["prizes"]
                        )
                        with st.expander(f"{l['name']} - {prizes}"):
                            # Mostrar motivación de cada premio
                            for p in l["prizes"]:
                                if p.get("motivation"):
                                    st.markdown(f"**{p['category']} ({p['year']}):** {p['motivation']}")
                except Exception as e:
                    st.error(f"Search failed: {e}")

    # =========================================================================
    # PESTAÑA 2: MEDALLA FIELDS (WIKIDATA)
    # =========================================================================
    with tab2:
        st.subheader("Fields Medal Winners")

        # Fields Medal se otorga cada 4 años desde 1936
        year = st.number_input("Year", value=None, min_value=1936, max_value=datetime.now().year, key="fields_year")

        if st.button("Search Fields Medal"):
            with st.spinner("Fetching from Wikidata..."):
                try:
                    params = {}
                    if year:
                        params["year"] = int(year)

                    results = api_request("/search/fields-medal", params=params)

                    st.subheader(f"Found {results['count']} winners")

                    # Lista simple de ganadores
                    for w in results["winners"]:
                        st.markdown(
                            f"- **{w['name']}** ({w.get('year', 'N/A')}) - {w.get('affiliation', 'N/A')}"
                        )
                except Exception as e:
                    st.error(f"Search failed: {e}")

    # =========================================================================
    # PESTAÑA 3: PREMIO TURING (WIKIDATA)
    # =========================================================================
    with tab3:
        st.subheader("Turing Award Winners")

        # Turing Award desde 1966
        year = st.number_input("Year", value=None, min_value=1966, max_value=datetime.now().year, key="turing_year")

        if st.button("Search Turing Award"):
            with st.spinner("Fetching from Wikidata..."):
                try:
                    params = {}
                    if year:
                        params["year"] = int(year)

                    results = api_request("/search/turing-award", params=params)

                    st.subheader(f"Found {results['count']} winners")
                    for w in results["winners"]:
                        st.markdown(
                            f"- **{w['name']}** ({w.get('year', 'N/A')}) - {w.get('affiliation', 'N/A')}"
                        )
                except Exception as e:
                    st.error(f"Search failed: {e}")

    # =========================================================================
    # PESTAÑA 4: OTROS PREMIOS POR Q-ID (WIKIDATA GENÉRICO)
    # =========================================================================
    with tab4:
        st.subheader("Search by Wikidata Q-ID")

        # Guía de Q-IDs comunes
        st.markdown("""
        Common prize Q-IDs:
        - **Q28835**: Fields Medal
        - **Q185667**: Turing Award
        - **Q160042**: Abel Prize
        - **Q15046788**: Breakthrough Prize (Math)
        - **Q194351**: Wolf Prize (Math)
        - **Q694251**: Wolf Prize (Physics)
        """)

        # Input para Q-ID (con default al Abel Prize)
        qid = st.text_input("Prize Q-ID", value="Q160042")
        year = st.number_input("Year", value=None, min_value=1900, max_value=datetime.now().year, key="other_year")

        if st.button("Search Prize"):
            with st.spinner("Fetching from Wikidata..."):
                try:
                    params = {"year": int(year)} if year else {}
                    results = api_request(f"/search/prizes/{qid}", params=params)

                    st.subheader(f"Found {results['count']} winners")
                    for w in results["winners"]:
                        st.markdown(
                            f"- **{w['name']}** ({w.get('year', 'N/A')})"
                        )
                        # Mostrar descripción si está disponible
                        if w.get("description"):
                            st.caption(w["description"])
                except Exception as e:
                    st.error(f"Search failed: {e}")


# =============================================================================
# PÁGINA: STATS - Estadísticas del sistema
# =============================================================================

def render_stats():
    """
    Renderiza las estadísticas del sistema RAG.

    MÉTRICAS MOSTRADAS:
    ===================

    ┌─────────────────────────────────────────────────────────────────────┐
    │                     SYSTEM STATISTICS                               │
    ├──────────────────────────────┬──────────────────────────────────────┤
    │      VECTOR STORE            │         EMBEDDINGS                   │
    │                              │                                      │
    │  ┌────────────────────┐     │  ┌────────────────────┐              │
    │  │ Indexed Chunks     │     │  │ Model              │              │
    │  │       25,000       │     │  │    BAAI/bge-m3     │              │
    │  └────────────────────┘     │  └────────────────────┘              │
    │                              │                                      │
    │  ┌────────────────────┐     │  ┌────────────────────┐              │
    │  │ Semantic Cache     │     │  │ Cache Size         │              │
    │  │       1,500        │     │  │       5,200        │              │
    │  └────────────────────┘     │  └────────────────────┘              │
    │                              │                                      │
    │  ┌────────────────────┐     │                                      │
    │  │ Retrieval Cache    │     │                                      │
    │  │         50         │     │                                      │
    │  └────────────────────┘     │                                      │
    │                              │                                      │
    └──────────────────────────────┴──────────────────────────────────────┘

    ST.METRIC:
    ==========

    st.metric crea un widget de métrica con:
    - Label (nombre de la métrica)
    - Value (valor actual)
    - Delta (cambio opcional, con flecha arriba/abajo)

    Ejemplo:
        st.metric("Temperature", "70 °F", "1.2 °F")
        # Muestra: Temperature
        #          70 °F
        #          ▲ 1.2 °F (en verde)

    INTERPRETACIÓN DE MÉTRICAS:
    ===========================

    Indexed Chunks: Total de chunks en LanceDB
        - Más chunks = más información disponible para RAG
        - Cada paper genera ~5-50 chunks dependiendo de longitud

    Semantic Cache: Queries cacheadas por similitud
        - Evita regenerar respuestas para preguntas similares
        - Alto número = muchas queries repetidas (bueno para perf)

    Retrieval Cache: Búsquedas cacheadas (TTL 30 min)
        - Evita recalcular embeddings de queries
        - Se limpia automáticamente después de 30 minutos

    Model: Modelo de embeddings activo
        - BAAI/bge-m3 = modelo multilingüe de alta calidad

    Cache Size: Embeddings cacheados en disco
        - Alto número = muchos textos procesados
        - Ahorra tiempo en re-procesamiento
    """
    st.header("System Statistics")

    try:
        # Obtener estadísticas del backend
        stats = api_request("/stats")

        # Dividir en 2 columnas
        col1, col2 = st.columns(2)

        # Columna izquierda: Vector Store
        with col1:
            st.subheader("Vector Store")
            vs = stats.get("vectorstore", {})

            # Métricas del vectorstore
            st.metric("Indexed Chunks", vs.get("chunks_count", 0))
            st.metric("Semantic Cache", vs.get("semantic_cache_count", 0))
            st.metric("Retrieval Cache", vs.get("retrieval_cache_size", 0))

        # Columna derecha: Embeddings
        with col2:
            st.subheader("Embeddings")
            emb = stats.get("embeddings", {})

            # Métricas del servicio de embeddings
            st.metric("Model", emb.get("model", "N/A"))
            st.metric("Cache Size", emb.get("cache_size", 0))

    except Exception as e:
        # Si el backend no responde, mostrar error
        st.error(f"Failed to load stats: {e}")


# =============================================================================
# FUNCIÓN PRINCIPAL - Punto de entrada de Streamlit
# =============================================================================

def main():
    """
    Función principal de la aplicación Streamlit.

    ESTRUCTURA DE UNA APP STREAMLIT:
    ================================

        main()
          │
          ├── st.set_page_config()     # Configuración de página (DEBE SER PRIMERO)
          │
          ├── init_session_state()      # Inicializar estado persistente
          │
          ├── st.title() / st.header()  # Elementos de layout
          │
          ├── st.sidebar.*              # Navegación en sidebar
          │
          └── render_*()                # Renderizar página seleccionada

    ST.SET_PAGE_CONFIG:
    ===================

    IMPORTANTE: Debe ser la PRIMERA llamada a Streamlit en el script.
    Si hay cualquier otro st.* antes, lanza error.

    Parámetros:
    - page_title: Título en la pestaña del navegador
    - page_icon: Emoji o path a imagen para favicon
    - layout: "centered" (default, columna angosta) o "wide" (full width)
    - initial_sidebar_state: "auto", "expanded", "collapsed"

    LAYOUT WIDE VS CENTERED:
    ========================

    Centered (default):
    ┌─────────────────────────────────────────────────────────────────┐
    │  │                                                         │   │
    │  │            ┌───────────────────────────┐                │   │
    │  │            │         CONTENT           │                │   │
    │  │            │      (max ~700px)         │                │   │
    │  │            └───────────────────────────┘                │   │
    │  │                                                         │   │
    └─────────────────────────────────────────────────────────────────┘

    Wide:
    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │                       CONTENT                            │   │
    │  │                  (full browser width)                    │   │
    │  └─────────────────────────────────────────────────────────┘   │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘

    SIDEBAR:
    ========

    st.sidebar.* renderiza elementos en la barra lateral.
    Es útil para:
    - Navegación entre páginas
    - Filtros globales
    - Configuración
    - Información de estado

    FLUJO DE NAVEGACIÓN:
    ====================

        Usuario selecciona página en sidebar
                     │
                     ▼
        ┌─────────────────────────────┐
        │    page = st.sidebar.       │
        │    selectbox(...)           │
        └─────────────┬───────────────┘
                      │
          ┌───────────┼───────────┬───────────┬───────────┐
          ▼           ▼           ▼           ▼           ▼
       "Chat"     "Search"    "Ingest"   "Prizes"    "Stats"
          │           │           │           │           │
          ▼           ▼           ▼           ▼           ▼
    render_chat() render_   render_    render_    render_
                  search()  ingest()   prizes()   stats()
    """
    # =========================================================================
    # CONFIGURACIÓN DE PÁGINA (DEBE SER PRIMERA LLAMADA A STREAMLIT)
    # =========================================================================
    st.set_page_config(
        page_title="Scientific Library RAG",  # Título en pestaña del browser
        page_icon="📚",                        # Favicon (emoji o path)
        layout="wide",                         # Usar ancho completo
    )

    # =========================================================================
    # INICIALIZAR SESSION STATE
    # =========================================================================
    # Esto debe ejecutarse en cada re-run para asegurar que las variables existen
    init_session_state()

    # =========================================================================
    # HEADER PRINCIPAL
    # =========================================================================
    st.title("📚 Scientific Library RAG")
    st.markdown("*Biblioteca Científica Offline con Sistema RAG Local*")

    # =========================================================================
    # SIDEBAR: NAVEGACIÓN
    # =========================================================================
    # Selectbox en sidebar para cambiar entre páginas
    page = st.sidebar.selectbox(
        "Navigation",
        ["Chat", "Search", "Ingest", "Prizes", "Stats"],
    )

    # =========================================================================
    # SIDEBAR: ESTADO DEL API
    # =========================================================================
    # Verificar si el backend está disponible
    try:
        health = api_request("/health")
        # Si responde, mostrar estado en verde
        st.sidebar.success(f"API: {health['status']}")
        st.sidebar.caption(f"Model: {health['embedding_model']}")
    except Exception:
        # Si no responde, mostrar error en rojo con instrucciones
        st.sidebar.error("API not available")
        st.sidebar.caption("Start API with: uvicorn app.main:app")

    # =========================================================================
    # TUTORIAL DE BIENVENIDA (solo primera visita)
    # =========================================================================
    show_welcome_tutorial()

    # =========================================================================
    # RENDERIZAR PÁGINA SELECCIONADA
    # =========================================================================
    # Mostrar tip de la página actual
    show_page_tip(page)

    # Cada página tiene su propia función de render
    if page == "Chat":
        render_chat()      # Interfaz conversacional RAG
    elif page == "Search":
        render_search()    # Búsqueda de papers
    elif page == "Ingest":
        render_ingest()    # Ingestión de PDFs
    elif page == "Prizes":
        render_prizes()    # Explorador de premios
    elif page == "Stats":
        render_stats()     # Estadísticas del sistema


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================
#
# En Streamlit, este bloque es técnicamente innecesario porque
# streamlit run ejecuta todo el script de arriba a abajo.
#
# Sin embargo, es buena práctica incluirlo para:
# 1. Claridad sobre el punto de entrada
# 2. Compatibilidad si alguien ejecuta con python directamente
# 3. Permitir importar el módulo sin ejecutar main()

if __name__ == "__main__":
    main()
