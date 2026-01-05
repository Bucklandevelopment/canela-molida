#!/bin/bash
# Scientific Library RAG - Setup Script

set -e

echo "🔬 Scientific Library RAG - Setup"
echo "=================================="

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python version: $python_version"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create data directories
echo "Creating data directories..."
mkdir -p data/pdfs data/markdown data/vectors
mkdir -p metadata
mkdir -p .cache/embeddings

# Check Ollama
echo ""
echo "Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama is installed"

    # Check if models are available
    echo "Checking models..."
    if ollama list | grep -q "bge-m3"; then
        echo "✅ bge-m3 is available"
    else
        echo "⚠️  bge-m3 not found. Run: ollama pull bge-m3"
    fi

    if ollama list | grep -q "llama3.1"; then
        echo "✅ llama3.1 is available"
    else
        echo "⚠️  llama3.1 not found. Run: ollama pull llama3.1:8b"
    fi
else
    echo "⚠️  Ollama not found. Install from: https://ollama.ai"
fi

# Check Docker (optional)
echo ""
echo "Checking Docker..."
if command -v docker &> /dev/null; then
    echo "✅ Docker is installed"
    echo "   To start GROBID: docker run -p 8070:8070 grobid/grobid:0.8.2-full"
else
    echo "ℹ️  Docker not found (optional, for GROBID)"
fi

echo ""
echo "=================================="
echo "✅ Setup complete!"
echo ""
echo "To start the API:"
echo "  source .venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo "To start the frontend:"
echo "  streamlit run frontend/app.py"
echo ""
echo "Or use Docker Compose:"
echo "  cd config && docker-compose up -d"
