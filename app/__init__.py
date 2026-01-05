"""
Scientific Library RAG - Biblioteca Científica Offline con Sistema RAG Local

Stack: FastAPI + LanceDB + BGE-M3 + Ollama

Arquitectura:
- Backend API: FastAPI con uvicorn async
- Vector DB: LanceDB (embedded, disk-native)
- Embeddings: BGE-M3 vía Ollama (1024 dims, 8K context, 100+ idiomas)
- LLM: Llama 3.1 8B o Qwen3 8B vía Ollama
- PDF Processing: GROBID (metadatos) + PyMuPDF4LLM (texto)
- Frontend: Streamlit
"""

__version__ = "1.0.0"
