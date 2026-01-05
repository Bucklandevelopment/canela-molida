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
│   │   └── pdf_processor.py    # Procesamiento de PDFs
│   ├── models/                 # Modelos Pydantic
│   └── core/                   # Configuracion
│       └── config.py
├── frontend/                   # Frontend Streamlit
│   └── app.py
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
| Frontend Streamlit | 8501 | Interfaz web |
| Ollama | 11434 | Servidor de modelos LLM |
| GROBID | 8070 | Extraccion de metadatos PDF |

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
