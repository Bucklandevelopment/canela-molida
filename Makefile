# Scientific Library RAG - Makefile
# Comandos de mantenimiento para el proyecto

.PHONY: help install setup api frontend dev test lint format clean \
        docker-up docker-up-cpu docker-down docker-logs docker-build \
        ollama-pull grobid-start grobid-stop check \
        soft-reset hard-reset run-all

# Variables
PYTHON := python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTHON_VENV := $(VENV)/bin/python
UVICORN := $(VENV)/bin/uvicorn
STREAMLIT := $(VENV)/bin/streamlit
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff

# Colores para output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

# Default target
help:
	@echo "$(CYAN)Scientific Library RAG - Comandos disponibles$(RESET)"
	@echo ""
	@echo "$(GREEN)Setup:$(RESET)"
	@echo "  make install      - Crear venv e instalar dependencias"
	@echo "  make setup        - Setup completo (install + dirs + check)"
	@echo "  make ollama-pull  - Descargar modelos de Ollama"
	@echo ""
	@echo "$(GREEN)Desarrollo:$(RESET)"
	@echo "  make run-all      - Iniciar API + Frontend en paralelo"
	@echo "  make api          - Iniciar API FastAPI (puerto 3690)"
	@echo "  make frontend     - Iniciar frontend Streamlit (puerto 8501)"
	@echo "  make dev          - Iniciar API con hot-reload"
	@echo ""
	@echo "$(GREEN)Testing y Calidad:$(RESET)"
	@echo "  make test         - Ejecutar tests"
	@echo "  make lint         - Verificar codigo con ruff"
	@echo "  make format       - Formatear codigo con ruff"
	@echo "  make check        - Verificar dependencias y servicios"
	@echo ""
	@echo "$(GREEN)Docker:$(RESET)"
	@echo "  make docker-up      - Levantar con Docker (GPU)"
	@echo "  make docker-up-cpu  - Levantar con Docker (CPU only)"
	@echo "  make docker-down    - Detener contenedores"
	@echo "  make docker-logs    - Ver logs de contenedores"
	@echo "  make docker-build   - Reconstruir imagenes"
	@echo ""
	@echo "$(GREEN)Servicios externos:$(RESET)"
	@echo "  make grobid-start - Iniciar GROBID en Docker"
	@echo "  make grobid-stop  - Detener GROBID"
	@echo ""
	@echo "$(GREEN)Limpieza:$(RESET)"
	@echo "  make clean        - Limpiar archivos temporales"
	@echo "  make clean-all    - Limpiar todo (incluyendo venv y cache)"
	@echo ""
	@echo "$(GREEN)Reset:$(RESET)"
	@echo "  make soft-reset   - Limpiar cache + reinstalar dependencias"
	@echo "  make hard-reset   - Limpiar TODO + Docker volumes + setup completo"

# ============================================================================
# Setup
# ============================================================================

install: $(VENV)/bin/activate

$(VENV)/bin/activate:
	@echo "$(CYAN)Creando entorno virtual...$(RESET)"
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)Dependencias instaladas$(RESET)"

setup: install
	@echo "$(CYAN)Configurando proyecto...$(RESET)"
	@mkdir -p data/pdfs data/markdown data/vectors
	@mkdir -p metadata
	@mkdir -p .cache/embeddings
	@cp -n .env.example .env 2>/dev/null || true
	@echo "$(GREEN)Setup completo$(RESET)"
	@$(MAKE) check

ollama-pull:
	@echo "$(CYAN)Descargando modelos de Ollama...$(RESET)"
	ollama pull bge-m3
	ollama pull llama3.1:8b
	@echo "$(GREEN)Modelos descargados$(RESET)"

# ============================================================================
# Desarrollo
# ============================================================================

api: $(VENV)/bin/activate
	@echo "$(CYAN)Iniciando API en http://localhost:3690$(RESET)"
	$(UVICORN) app.main:app --host 0.0.0.0 --port 3690

dev: $(VENV)/bin/activate
	@echo "$(CYAN)Iniciando API en modo desarrollo...$(RESET)"
	$(UVICORN) app.main:app --host 0.0.0.0 --port 3690 --reload

frontend: $(VENV)/bin/activate
	@echo "$(CYAN)Iniciando frontend en http://localhost:8501$(RESET)"
	$(STREAMLIT) run frontend/app.py --server.port 8501 --server.address 0.0.0.0

run-all: $(VENV)/bin/activate
	@echo "$(CYAN)======================================$(RESET)"
	@echo "$(CYAN)  Iniciando API + Frontend           $(RESET)"
	@echo "$(CYAN)======================================$(RESET)"
	@echo ""
	@echo "$(GREEN)API:$(RESET)      http://localhost:3690"
	@echo "$(GREEN)Frontend:$(RESET) http://localhost:8501"
	@echo "$(GREEN)Docs:$(RESET)     http://localhost:3690/docs"
	@echo ""
	@echo "$(YELLOW)Presiona Ctrl+C para detener ambos servicios$(RESET)"
	@echo ""
	@trap 'kill 0' INT; \
	$(UVICORN) app.main:app --host 0.0.0.0 --port 3690 & \
	$(STREAMLIT) run frontend/app.py --server.port 8501 --server.address 0.0.0.0 & \
	wait

# ============================================================================
# Testing y Calidad
# ============================================================================

test: $(VENV)/bin/activate
	@echo "$(CYAN)Ejecutando tests...$(RESET)"
	$(PYTEST) tests/ -v

test-cov: $(VENV)/bin/activate
	@echo "$(CYAN)Ejecutando tests con coverage...$(RESET)"
	$(PYTEST) tests/ -v --cov=app --cov-report=html

lint: $(VENV)/bin/activate
	@echo "$(CYAN)Verificando codigo...$(RESET)"
	$(RUFF) check app/ frontend/ tests/

format: $(VENV)/bin/activate
	@echo "$(CYAN)Formateando codigo...$(RESET)"
	$(RUFF) format app/ frontend/ tests/
	$(RUFF) check --fix app/ frontend/ tests/

check:
	@echo "$(CYAN)Verificando servicios...$(RESET)"
	@echo ""
	@echo "Python: $$($(PYTHON) --version)"
	@echo ""
	@if command -v ollama &> /dev/null; then \
		echo "$(GREEN)Ollama: instalado$(RESET)"; \
		if ollama list 2>/dev/null | grep -q "bge-m3"; then \
			echo "  - bge-m3: $(GREEN)disponible$(RESET)"; \
		else \
			echo "  - bge-m3: $(YELLOW)no encontrado (ollama pull bge-m3)$(RESET)"; \
		fi; \
		if ollama list 2>/dev/null | grep -q "llama3.1"; then \
			echo "  - llama3.1: $(GREEN)disponible$(RESET)"; \
		else \
			echo "  - llama3.1: $(YELLOW)no encontrado (ollama pull llama3.1:8b)$(RESET)"; \
		fi; \
	else \
		echo "$(YELLOW)Ollama: no instalado (https://ollama.ai)$(RESET)"; \
	fi
	@echo ""
	@if command -v docker &> /dev/null; then \
		echo "$(GREEN)Docker: instalado$(RESET)"; \
		if docker ps 2>/dev/null | grep -q "grobid"; then \
			echo "  - GROBID: $(GREEN)corriendo$(RESET)"; \
		else \
			echo "  - GROBID: $(YELLOW)no corriendo (make grobid-start)$(RESET)"; \
		fi; \
	else \
		echo "$(YELLOW)Docker: no instalado (opcional para GROBID)$(RESET)"; \
	fi

# ============================================================================
# Docker
# ============================================================================

docker-up:
	@echo "$(CYAN)Levantando servicios con GPU...$(RESET)"
	cd config && docker compose up -d

docker-up-cpu:
	@echo "$(CYAN)Levantando servicios (CPU only)...$(RESET)"
	cd config && docker compose -f docker-compose.cpu.yml up -d

docker-down:
	@echo "$(CYAN)Deteniendo servicios...$(RESET)"
	cd config && docker compose down

docker-logs:
	cd config && docker compose logs -f

docker-build:
	@echo "$(CYAN)Reconstruyendo imagenes...$(RESET)"
	cd config && docker compose build --no-cache

docker-ps:
	cd config && docker compose ps

# ============================================================================
# Servicios externos
# ============================================================================

grobid-start:
	@echo "$(CYAN)Iniciando GROBID...$(RESET)"
	docker run -d --name grobid -p 8070:8070 grobid/grobid:0.8.2-full
	@echo "$(GREEN)GROBID disponible en http://localhost:8070$(RESET)"

grobid-stop:
	@echo "$(CYAN)Deteniendo GROBID...$(RESET)"
	docker stop grobid && docker rm grobid

# ============================================================================
# Limpieza
# ============================================================================

clean:
	@echo "$(CYAN)Limpiando archivos temporales...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".ruff_cache" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	@echo "$(GREEN)Limpieza completada$(RESET)"

clean-all: clean
	@echo "$(CYAN)Limpieza profunda...$(RESET)"
	rm -rf $(VENV)
	rm -rf .cache/
	rm -rf data/vectors/
	@echo "$(GREEN)Limpieza profunda completada$(RESET)"

# ============================================================================
# Reset - Limpieza + Setup automatico
# ============================================================================

soft-reset:
	@echo "$(CYAN)======================================$(RESET)"
	@echo "$(CYAN)       SOFT RESET - Inicio           $(RESET)"
	@echo "$(CYAN)======================================$(RESET)"
	@echo ""
	@echo "$(YELLOW)Paso 1/4: Limpiando archivos de cache...$(RESET)"
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -f .coverage 2>/dev/null || true
	@rm -rf htmlcov/ 2>/dev/null || true
	@rm -rf .cache/embeddings/* 2>/dev/null || true
	@echo "$(GREEN)  Cache limpiado$(RESET)"
	@echo ""
	@echo "$(YELLOW)Paso 2/4: Actualizando dependencias...$(RESET)"
	@if [ -d "$(VENV)" ]; then \
		$(PIP) install --upgrade pip; \
		$(PIP) install -r requirements.txt --upgrade; \
		echo "$(GREEN)  Dependencias actualizadas$(RESET)"; \
	else \
		$(PYTHON) -m venv $(VENV); \
		$(PIP) install --upgrade pip; \
		$(PIP) install -r requirements.txt; \
		echo "$(GREEN)  Entorno virtual creado y dependencias instaladas$(RESET)"; \
	fi
	@echo ""
	@echo "$(YELLOW)Paso 3/4: Verificando directorios...$(RESET)"
	@mkdir -p data/pdfs data/markdown data/vectors
	@mkdir -p metadata
	@mkdir -p .cache/embeddings
	@echo "$(GREEN)  Directorios verificados$(RESET)"
	@echo ""
	@echo "$(YELLOW)Paso 4/4: Verificando servicios...$(RESET)"
	@$(MAKE) check --no-print-directory
	@echo ""
	@echo "$(CYAN)======================================$(RESET)"
	@echo "$(GREEN)  SOFT RESET - Completado!          $(RESET)"
	@echo "$(CYAN)======================================$(RESET)"
	@echo ""
	@echo "Ejecuta:"
	@echo "  make api       - Iniciar backend"
	@echo "  make frontend  - Iniciar frontend"

hard-reset:
	@echo "$(CYAN)======================================$(RESET)"
	@echo "$(CYAN)       HARD RESET - Inicio           $(RESET)"
	@echo "$(CYAN)======================================$(RESET)"
	@echo ""
	@echo "$(YELLOW)Paso 1/7: Deteniendo contenedores Docker...$(RESET)"
	@if command -v docker &> /dev/null; then \
		docker stop grobid 2>/dev/null || true; \
		docker rm grobid 2>/dev/null || true; \
		cd config && docker compose down 2>/dev/null || true; \
		echo "$(GREEN)  Contenedores detenidos$(RESET)"; \
	else \
		echo "$(YELLOW)  Docker no disponible, saltando...$(RESET)"; \
	fi
	@echo ""
	@echo "$(YELLOW)Paso 2/7: Eliminando volumenes Docker...$(RESET)"
	@if command -v docker &> /dev/null; then \
		docker volume rm sci-library-ollama-data 2>/dev/null || true; \
		echo "$(GREEN)  Volumenes eliminados$(RESET)"; \
	else \
		echo "$(YELLOW)  Docker no disponible, saltando...$(RESET)"; \
	fi
	@echo ""
	@echo "$(YELLOW)Paso 3/7: Eliminando entorno virtual...$(RESET)"
	@rm -rf $(VENV)
	@echo "$(GREEN)  Entorno virtual eliminado$(RESET)"
	@echo ""
	@echo "$(YELLOW)Paso 4/7: Eliminando cache y datos temporales...$(RESET)"
	@rm -rf .cache/
	@rm -rf data/vectors/
	@rm -rf htmlcov/
	@rm -f .coverage
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)  Cache y datos eliminados$(RESET)"
	@echo ""
	@echo "$(YELLOW)Paso 5/7: Creando entorno virtual...$(RESET)"
	@$(PYTHON) -m venv $(VENV)
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)  Entorno virtual creado$(RESET)"
	@echo ""
	@echo "$(YELLOW)Paso 6/7: Configurando directorios...$(RESET)"
	@mkdir -p data/pdfs data/markdown data/vectors
	@mkdir -p metadata
	@mkdir -p .cache/embeddings
	@cp -n .env.example .env 2>/dev/null || true
	@echo "$(GREEN)  Directorios configurados$(RESET)"
	@echo ""
	@echo "$(YELLOW)Paso 7/7: Verificando servicios...$(RESET)"
	@$(MAKE) check --no-print-directory
	@echo ""
	@echo "$(CYAN)======================================$(RESET)"
	@echo "$(GREEN)  HARD RESET - Completado!          $(RESET)"
	@echo "$(CYAN)======================================$(RESET)"
	@echo ""
	@echo "Siguiente pasos:"
	@echo "  1. make ollama-pull   - Descargar modelos (si es necesario)"
	@echo "  2. make grobid-start  - Iniciar GROBID (opcional)"
	@echo "  3. make api           - Iniciar backend"
	@echo "  4. make frontend      - Iniciar frontend"
