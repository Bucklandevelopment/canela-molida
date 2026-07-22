# Scientific Library RAG

Biblioteca Cientifica Offline con Sistema RAG Local.

**Stack:** FastAPI + LanceDB + BGE-M3 + Ollama + GROBID

## Features

- **Paper Discovery**: Busqueda en OpenAlex (240M+ papers), arXiv (2.5M+), PubMed
- **PDF Processing**: GROBID para metadatos, PyMuPDF4LLM para extraccion de texto
- **Vector Search**: LanceDB con embeddings BGE-M3 (1024 dims, 8K context)
- **RAG Q&A**: Busqueda semantica + generacion con LLM local (Ollama)
- **Scientific Prizes**: API Nobel, Wikidata SPARQL para Fields Medal, Turing, etc.
- **Caching**: Cache de embeddings, retrieval cache (30min TTL), semantic cache
- **100% Offline**: Una vez descargados los papers, funciona sin conexion

---

## Inicio Rapido (5 minutos)

### Prerequisitos

Antes de empezar, asegurate de tener instalado:

| Requisito | Version | Verificar | Instalar |
|-----------|---------|-----------|----------|
| Python | 3.10+ | `python3 --version` | [python.org](https://python.org) |
| Ollama | latest | `ollama --version` | [ollama.ai](https://ollama.ai) |
| Docker | (opcional) | `docker --version` | [docker.com](https://docker.com) |
| Make | any | `make --version` | Incluido en macOS/Linux |

### Paso 1: Clonar el repositorio

```bash
git clone <repo-url>
cd canela-molida
```

### Paso 2: Setup automatico

```bash
make setup
```

Esto automaticamente:
- Crea el entorno virtual (`.venv/`)
- Instala todas las dependencias
- Crea los directorios necesarios
- Copia `.env.example` a `.env`
- Verifica el estado de los servicios

### Paso 3: Descargar modelos de Ollama

```bash
# Asegurate de que Ollama este corriendo
ollama serve  # En otra terminal si no esta corriendo

# Descargar modelos (puede tardar unos minutos)
make ollama-pull
```

Esto descarga:
- `bge-m3`: Modelo de embeddings multilingue (requerido)
- `llama3.1:8b`: Modelo de lenguaje para generacion (requerido)

### Paso 4: Iniciar la aplicacion

```bash
make run-all
```

Esto inicia API y Frontend en paralelo. Accede a:

| Servicio | URL |
|----------|-----|
| **Frontend** | http://localhost:8501 |
| **API Docs** | http://localhost:3690/docs |
| **API ReDoc** | http://localhost:3690/redoc |

Presiona `Ctrl+C` para detener ambos servicios.

### (Opcional) Paso 5: Iniciar GROBID

GROBID mejora la extraccion de metadatos de PDFs (titulo, autores, abstract, referencias).

```bash
make grobid-start
```

---

## Primeros Pasos: Como usar la aplicacion

**IMPORTANTE:** Este es un sistema RAG (Retrieval Augmented Generation). Necesitas **ingestar papers primero** antes de poder hacer preguntas sobre ellos.

### Flujo de uso

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FLUJO DE USO DEL SISTEMA                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. INGESTAR PAPERS                                                    │
│      │                                                                  │
│      ├── Subir PDF local (seccion "Ingest")                            │
│      │   └── Sube archivos PDF desde tu ordenador                      │
│      │                                                                  │
│      └── Descargar de arXiv (seccion "Ingest")                         │
│          └── Introduce IDs de arXiv (ej: 2301.00001)                   │
│                                                                         │
│                          ▼                                              │
│                                                                         │
│   2. EL SISTEMA PROCESA LOS PAPERS                                      │
│      │                                                                  │
│      ├── Extrae texto del PDF                                          │
│      ├── Divide en chunks de ~1000 caracteres                          │
│      ├── Genera embeddings con BGE-M3                                  │
│      └── Indexa en la base de datos vectorial (LanceDB)                │
│                                                                         │
│                          ▼                                              │
│                                                                         │
│   3. HAZ PREGUNTAS (seccion "Chat")                                     │
│      │                                                                  │
│      └── El sistema busca chunks relevantes en tus papers              │
│          y genera respuestas basadas en ese contexto                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Ejemplo practico

1. **Abre la aplicacion:** http://localhost:8501

2. **Ve a "Ingest"** y descarga un paper de arXiv:
   ```
   arXiv ID: 1706.03762
   ```
   (Este es "Attention Is All You Need", el paper de Transformers)

3. **Espera a que procese** (~30-60 segundos)

4. **Ve a "Chat"** y pregunta:
   ```
   What is the main contribution of the Transformer architecture?
   ```

5. **El sistema responde** usando el contenido del paper que acabas de ingestar.

### Sin papers = sin respuestas

Si haces una pregunta sin haber ingestado papers, el sistema no tendra contexto para responder. Puedes verificar cuantos papers tienes indexados en la seccion **"Stats"**:

- `Indexed Chunks: 0` = No hay papers, necesitas ingestar
- `Indexed Chunks: 150` = Tienes papers indexados, puedes hacer preguntas

---

## Automatizacion de Instagram

El sistema puede convertir papers ingestados (o recien descubiertos en arXiv) en
borradores de posts para Instagram: genera el caption en espanol con el LLM
local y la imagen 1:1 con un backend de Stable Diffusion. Los borradores
**nunca** se publican solos — se revisan y aprueban desde un dashboard
Streamlit aparte. La publicacion final usa la Instagram Graph API (cuenta
Business o Creator).

### Pipeline

```
┌──────────────────────────────────────────────────────────────────────┐
│  1. SCHEDULER (opcional, off por defecto)                            │
│     └── APScheduler dispara cada N minutos                            │
│                                                                       │
│  2. PLANNER (app/services/content/planner.py)                        │
│     └── Elige paper local; si no hay, descubre arXiv por categoria   │
│                                                                       │
│  3. GENERATOR (app/services/content/generator.py)                    │
│     ├── Lee chunks del paper desde LanceDB                           │
│     └── Llama Ollama (llama3.1:8b) con prompts/instagram_post.md     │
│         → JSON {hook, caption, hashtags, alt_text, image_prompt}     │
│                                                                       │
│  4. RENDERER (app/services/content/renderer.py)                      │
│     └── POST a Stable Diffusion WebUI (AUTOMATIC1111)                │
│         → PNG 1080x1080 en data/instagram/images/                    │
│                                                                       │
│  5. STORE (app/services/content/store.py)                            │
│     └── SQLite en data/instagram/posts.sqlite (status=draft)         │
│                                                                       │
│  6. DASHBOARD (frontend/instagram_app.py, puerto 8502)               │
│     └── Preview, regenerar caption/imagen, aprobar, descartar         │
│                                                                       │
│  7. PUBLISHER (app/services/content/publisher.py)                    │
│     └── Solo cuando apruebas con "publish_now" o llamas /publish:    │
│         POST /{ig-user-id}/media → /media_publish (Graph API v21.0)  │
└──────────────────────────────────────────────────────────────────────┘
```

### Requisitos

- **Ollama** corriendo con `llama3.1:8b` (ya requerido por el RAG).
- **Stable Diffusion WebUI** local con API HTTP habilitada
  (`./webui.sh --api`). Por defecto en `http://localhost:7860`. Cualquier
  backend compatible con `POST /sdapi/v1/txt2img` funciona.
- **Cuenta Instagram Business o Creator** conectada a una Facebook Page,
  con una Meta App propia y un *long-lived access token* con permisos
  `instagram_basic`, `instagram_content_publish`, `pages_show_list`.
- **URL publica** desde la que Meta pueda descargar las imagenes
  (un tunel tipo `cloudflared`/`ngrok`, o tu CDN). Los archivos se sirven
  via `GET /api/instagram/images/{filename}`.

> **Nota:** la creacion de la cuenta de Meta y la generacion del token la
> haces tu manualmente, por seguridad. El sistema solo *consume* el token.

### Configuracion (`.env`)

```bash
# Scheduler (opcional)
CONTENT_SCHEDULER_ENABLED=false        # true para auto-generar drafts
CONTENT_SCHEDULER_INTERVAL_MIN=360     # minutos entre generaciones (>=15)

# Backend de imagen (Stable Diffusion WebUI)
IMAGE_BASE_URL=http://localhost:7860
IMAGE_WIDTH=1080
IMAGE_HEIGHT=1080
IMAGE_STEPS=28
IMAGE_SAMPLER=DPM++ 2M Karras
IMAGE_CFG_SCALE=6.5
IMAGE_TIMEOUT=180
# IMAGE_MODEL=                         # opcional: nombre del checkpoint

# Instagram Graph API
IG_USER_ID=                            # id de la cuenta Business
IG_ACCESS_TOKEN=                       # long-lived access token
IG_PUBLIC_BASE_URL=                    # URL publica para servir imagenes
                                       # ej: https://tu-tunel.example.com
```

### Flujo de uso

1. Asegurate de tener al menos un paper ingestado (seccion "Ingest" del
   frontend principal en :8501) o usa `source: arxiv` para descubrir
   uno nuevo.
2. Levanta el dashboard de Instagram en otra terminal:
   ```bash
   make frontend-instagram   # http://localhost:8502
   ```
3. En el sidebar, **Generate**:
   - `Source: local` — toma cualquier paper indexado sin draft previo.
   - `Source: arxiv` + `category` (ej. `cs.AI`) — descubre uno reciente.
   - `arXiv id` o `paper_id` — fija exactamente cual.
   - `Editorial notes` — instrucciones extras para el LLM.
4. El draft aparece con preview de imagen, caption y hashtags. Acciones:
   - **Aprobar** → cambia status a `approved` (no publica).
   - **Aprobar + publicar** → aprueba y dispara el publisher en background.
   - **Regenerar caption** / **Regenerar imagen** → reusa el mismo paper.
   - **Descartar** → marca `rejected`.
5. Una vez publicado el `permalink` aparece en el panel de detalles.

### Endpoints (`/api/instagram/*`)

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/api/instagram/drafts` | POST | Generar nuevo draft (body: `GenerateRequest`) |
| `/api/instagram/drafts` | GET | Listar drafts (filtro `status`, `limit`) |
| `/api/instagram/drafts/{id}` | GET | Detalle de un draft |
| `/api/instagram/drafts/{id}` | DELETE | Eliminar draft |
| `/api/instagram/drafts/{id}/regenerate` | POST | Regenerar caption y/o imagen |
| `/api/instagram/drafts/{id}/approve` | POST | Aprobar (`publish_now: true` para publicar) |
| `/api/instagram/drafts/{id}/reject` | POST | Marcar como descartado |
| `/api/instagram/drafts/{id}/publish` | POST | Publicar en Instagram (sincronico) |
| `/api/instagram/images/{filename}` | GET | Servir imagen del draft (preview + Graph API) |

Ejemplo cURL:

```bash
# Generar un draft a partir de un paper local
curl -X POST http://localhost:3690/api/instagram/drafts \
     -H "Content-Type: application/json" \
     -d '{"source": "local"}'

# Generar uno especifico desde arXiv
curl -X POST http://localhost:3690/api/instagram/drafts \
     -H "Content-Type: application/json" \
     -d '{"source": "arxiv", "arxiv_id": "1706.03762"}'

# Listar pendientes de revision
curl "http://localhost:3690/api/instagram/drafts?status=draft&limit=10"
```

### Datos persistidos

```
data/instagram/
├── posts.sqlite          # Drafts, status, ig_media_id, errores
└── images/
    └── {uuid}.png        # Imagenes generadas (1080x1080)
```

### Troubleshooting

**El sistema no genera nada / cuelga en "Generando…"**
- Confirma que Ollama esta arriba: `curl http://localhost:11434/api/tags`.
- Confirma que SD WebUI tiene la API on: `curl http://localhost:7860/sdapi/v1/sd-models`.
- Subi `IMAGE_TIMEOUT` si tu GPU es lenta.

**El JSON del LLM viene mal formado**
- El generador hace fallback con regex, pero si vuelve siempre roto, baja
  `temperature` (en `app/services/content/generator.py`) o cambia a un
  modelo mas instruct (ej. `qwen2.5:7b-instruct`).

**`Publisher not configured`**
- Faltan `IG_USER_ID`, `IG_ACCESS_TOKEN` o `IG_PUBLIC_BASE_URL` en `.env`.
  El draft queda en estado `failed` con el mensaje en `error`.

**Meta responde `Media URL is not accessible`**
- `IG_PUBLIC_BASE_URL` debe resolver desde internet a tu API. Verifica el
  tunel: `curl https://<tu-tunel>/api/instagram/images/<archivo>.png`.

**Quiero que el scheduler corra una sola vez al dia**
- `CONTENT_SCHEDULER_ENABLED=true` y `CONTENT_SCHEDULER_INTERVAL_MIN=1440`.

---

## Comandos Disponibles

Ejecuta `make help` para ver todos los comandos. Aqui estan organizados por categoria:

### Setup e Instalacion

| Comando | Descripcion |
|---------|-------------|
| `make setup` | Setup completo (venv + deps + dirs + verificacion) |
| `make install` | Solo crear venv e instalar dependencias |
| `make ollama-pull` | Descargar modelos de Ollama |
| `make check` | Verificar estado de servicios (Ollama, GROBID) |

### Desarrollo

| Comando | Descripcion |
|---------|-------------|
| `make run-all` | **Iniciar API + Frontend en paralelo** |
| `make api` | Iniciar solo API (puerto 3690) |
| `make frontend` | Iniciar solo Frontend (puerto 8501) |
| `make frontend-instagram` | Iniciar dashboard de drafts Instagram (puerto 8502) |
| `make dev` | Iniciar API con hot-reload |

### Testing y Calidad de Codigo

| Comando | Descripcion |
|---------|-------------|
| `make test` | Ejecutar tests |
| `make test-cov` | Tests con reporte de coverage |
| `make lint` | Verificar codigo con ruff |
| `make format` | Formatear codigo automaticamente |

### Docker

| Comando | Descripcion |
|---------|-------------|
| `make docker-up` | Levantar todo con Docker (requiere GPU NVIDIA) |
| `make docker-up-cpu` | Levantar con Docker (solo CPU) |
| `make docker-down` | Detener contenedores |
| `make docker-logs` | Ver logs en tiempo real |
| `make docker-build` | Reconstruir imagenes |
| `make docker-ps` | Ver estado de contenedores |

### Servicios Externos

| Comando | Descripcion |
|---------|-------------|
| `make grobid-start` | Iniciar GROBID en Docker |
| `make grobid-stop` | Detener GROBID |

### Limpieza y Reset

| Comando | Descripcion |
|---------|-------------|
| `make clean` | Limpiar archivos temporales (pyc, cache) |
| `make clean-all` | Limpiar todo (venv, cache, vectordb) |
| `make soft-reset` | **Limpiar cache + actualizar deps + setup** |
| `make hard-reset` | **Limpiar TODO + Docker volumes + setup desde cero** |

#### Diferencia entre soft-reset y hard-reset

**`make soft-reset`** - Limpieza ligera, mantiene el venv:
- Limpia: `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `*.pyc`
- Limpia: cache de embeddings
- Actualiza dependencias
- Verifica servicios
- **Tiempo:** ~30 segundos

**`make hard-reset`** - Limpieza total, reinstala todo:
- Detiene contenedores Docker
- Elimina volumenes Docker (modelos de Ollama en Docker)
- Elimina `.venv/` completo
- Elimina `.cache/` y `data/vectors/`
- Reinstala todo desde cero
- **Tiempo:** ~2-3 minutos

---

## Estructura del Proyecto

```
canela-molida/
├── app/                        # Backend FastAPI
│   ├── main.py                 # Entry point de la API
│   ├── api/                    # Routers
│   │   ├── papers.py           # Busqueda de papers externos
│   │   ├── rag.py              # Consultas RAG
│   │   ├── ingest.py           # Ingestion de PDFs
│   │   └── search.py           # Busqueda local + premios
│   ├── services/               # Logica de negocio
│   │   ├── embeddings.py       # Servicio BGE-M3
│   │   ├── vectorstore.py      # Servicio LanceDB
│   │   ├── rag.py              # Pipeline RAG
│   │   ├── pdf_processor.py    # Procesamiento de PDFs
│   │   └── content/            # Automatizacion Instagram
│   │       ├── planner.py      # Eleccion de paper (local + arXiv)
│   │       ├── generator.py    # LLM → caption + image_prompt
│   │       ├── renderer.py     # Cliente Stable Diffusion
│   │       ├── publisher.py    # Instagram Graph API
│   │       ├── store.py        # SQLite repo de drafts
│   │       └── scheduler.py    # APScheduler (job periodico)
│   ├── models/                 # Modelos Pydantic
│   └── core/                   # Configuracion
│       └── config.py
├── frontend/                   # Frontend Streamlit
│   ├── app.py                  # UI principal RAG (puerto 8501)
│   └── instagram_app.py        # Dashboard de drafts IG (puerto 8502)
├── prompts/                    # System prompts editoriales
│   └── instagram_post.md
├── config/                     # Configuracion Docker
│   ├── docker-compose.yml      # Con GPU
│   └── docker-compose.cpu.yml  # Solo CPU
├── data/                       # Datos (gitignored)
│   ├── pdfs/                   # PDFs descargados
│   ├── markdown/               # Texto extraido
│   └── vectors/                # Base de datos LanceDB
├── taxonomy/                   # Categorias cientificas
│   ├── arxiv_categories.json
│   └── scientific_prizes.json
├── tests/                      # Tests
├── scripts/                    # Scripts de utilidad
│   └── setup.sh
├── .env.example                # Variables de entorno (template)
├── .env                        # Variables de entorno (local, gitignored)
├── requirements.txt            # Dependencias Python
├── pyproject.toml              # Configuracion del proyecto
└── Makefile                    # Comandos de mantenimiento
```

---

## Endpoints de la API

### RAG (Retrieval Augmented Generation)

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/api/rag/query` | POST | Consulta RAG completa |
| `/api/rag/query/stream` | POST | Consulta RAG con streaming |
| `/api/rag/search` | POST | Solo busqueda vectorial |

### Papers (Busqueda Externa)

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/api/papers/search/openalex` | GET | Buscar en OpenAlex (240M+ papers) |
| `/api/papers/search/arxiv` | GET | Buscar en arXiv |
| `/api/papers/by-doi/{doi}` | GET | Paper por DOI |
| `/api/papers/by-arxiv/{id}` | GET | Paper por ID de arXiv |

### Ingestion

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/api/ingest/pdf` | POST | Subir e ingestar PDF |
| `/api/ingest/arxiv/{id}` | POST | Descargar e ingestar desde arXiv |
| `/api/ingest/batch/arxiv` | POST | Ingestar multiples papers |

### Busqueda Local y Premios

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/api/search/papers` | GET | Buscar en papers indexados |
| `/api/search/nobel` | GET | Premios Nobel |
| `/api/search/fields-medal` | GET | Medallas Fields |
| `/api/search/turing-award` | GET | Premios Turing |
| `/api/search/prizes/{qid}` | GET | Premios por Wikidata Q-ID |

### Instagram (Content Automation)

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/api/instagram/drafts` | POST | Generar nuevo draft (paper local o arXiv) |
| `/api/instagram/drafts` | GET | Listar drafts (filtra por `status`) |
| `/api/instagram/drafts/{id}` | GET | Detalle de un draft |
| `/api/instagram/drafts/{id}` | DELETE | Eliminar draft |
| `/api/instagram/drafts/{id}/regenerate` | POST | Regenerar caption y/o imagen |
| `/api/instagram/drafts/{id}/approve` | POST | Aprobar (opcional `publish_now`) |
| `/api/instagram/drafts/{id}/reject` | POST | Marcar como descartado |
| `/api/instagram/drafts/{id}/publish` | POST | Publicar a Instagram |
| `/api/instagram/images/{filename}` | GET | Servir PNG generado |

### Sistema

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/` | GET | Info de la API |
| `/health` | GET | Health check |
| `/stats` | GET | Estadisticas del sistema |

---

## Puertos

| Servicio | Puerto | Descripcion |
|----------|--------|-------------|
| API FastAPI | 3690 | Backend principal |
| Frontend Streamlit (RAG) | 8501 | Interfaz web principal |
| Frontend Streamlit (Instagram) | 8502 | Dashboard de drafts (`make frontend-instagram`) |
| Ollama | 11434 | Servidor de modelos LLM |
| GROBID | 8070 | Extraccion de metadatos PDF |
| Stable Diffusion WebUI | 7860 | Backend de imagen (opcional, IG) |

---

## Variables de Entorno

Copia `.env.example` a `.env` y ajusta segun necesites:

```bash
cp .env.example .env
```

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `DEBUG` | `false` | Modo debug (hot-reload) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL del servidor Ollama |
| `EMBEDDING_MODEL` | `bge-m3` | Modelo de embeddings |
| `LLM_MODEL` | `llama3.1:8b` | Modelo de lenguaje |
| `GROBID_URL` | `http://localhost:8070` | URL de GROBID |
| `RAG_TOP_K` | `10` | Chunks a recuperar por query |
| `RAG_MAX_CONTEXT_LENGTH` | `4096` | Longitud maxima de contexto |
| `CHUNK_SIZE` | `1000` | Tamano de chunks |
| `CHUNK_OVERLAP` | `200` | Overlap entre chunks |
| `RETRIEVAL_CACHE_TTL` | `1800` | TTL del cache (segundos) |
| `SEMANTIC_CACHE_THRESHOLD` | `0.95` | Threshold de similitud para cache |
| `CONTENT_SCHEDULER_ENABLED` | `false` | Activar generacion automatica de drafts |
| `CONTENT_SCHEDULER_INTERVAL_MIN` | `360` | Minutos entre generaciones (>=15) |
| `IMAGE_BASE_URL` | `http://localhost:7860` | Stable Diffusion WebUI URL |
| `IMAGE_WIDTH` / `IMAGE_HEIGHT` | `1080` | Tamano de la imagen generada |
| `IMAGE_STEPS` | `28` | Pasos de difusion |
| `IMAGE_SAMPLER` | `DPM++ 2M Karras` | Sampler de SD |
| `IMAGE_CFG_SCALE` | `6.5` | Classifier-free guidance |
| `IMAGE_TIMEOUT` | `180` | Timeout HTTP al SD (segundos) |
| `IG_USER_ID` | — | Instagram Business account id |
| `IG_ACCESS_TOKEN` | — | Long-lived access token |
| `IG_PUBLIC_BASE_URL` | — | URL publica para que Meta descargue imagenes |

---

## Troubleshooting

### Ollama no responde

```bash
# Verificar si Ollama esta corriendo
curl http://localhost:11434/api/tags

# Si no responde, iniciar Ollama
ollama serve

# Verificar modelos instalados
ollama list
```

### Error "Model not found"

```bash
# Descargar modelos necesarios
make ollama-pull

# O manualmente:
ollama pull bge-m3
ollama pull llama3.1:8b
```

### Puerto en uso

```bash
# Ver que esta usando el puerto
lsof -i :3690  # API
lsof -i :8501  # Frontend

# Matar proceso
kill -9 <PID>
```

### Problemas con dependencias

```bash
# Reset suave (actualiza deps)
make soft-reset

# Reset completo (reinstala todo)
make hard-reset
```

### GROBID no inicia

```bash
# Verificar Docker
docker ps

# Reiniciar GROBID
make grobid-stop
make grobid-start

# Ver logs
docker logs grobid
```

### Limpiar base de datos vectorial

```bash
# Eliminar vectores (requiere re-ingestar papers)
rm -rf data/vectors/

# O usar hard-reset para limpiar todo
make hard-reset
```

---

## Desarrollo

### Instalar dependencias de desarrollo

```bash
pip install -e ".[dev]"
```

### Ejecutar tests

```bash
make test          # Tests basicos
make test-cov      # Con coverage report
```

### Linting y formato

```bash
make lint          # Verificar errores
make format        # Auto-formatear
```

### Estructura de un nuevo endpoint

```python
# app/api/mi_router.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/mi-modulo", tags=["Mi Modulo"])

@router.get("/endpoint")
async def mi_endpoint():
    return {"mensaje": "hola"}
```

Registrar en `app/api/__init__.py` y `app/main.py`.

---

## Despliegue con Docker

### Con GPU (NVIDIA)

```bash
make docker-up
```

### Solo CPU

```bash
make docker-up-cpu
```

### Ver logs

```bash
make docker-logs
```

### Detener

```bash
make docker-down
```

---

## Licencia

MIT
