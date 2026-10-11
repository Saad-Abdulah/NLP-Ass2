#!/usr/bin/env bash
# One-time (or after clone) setup. Not needed every time you run the chat app.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${VENV_PYTHON:-/Users/saad/Desktop/Python/Virtual/venv/bin/python}"
PIP="${VENV_PIP:-/Users/saad/Desktop/Python/Virtual/venv/bin/pip}"

echo "Installing Python dependencies..."
"$PIP" install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama not found. Install: brew install ollama"
  exit 1
fi

MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
if ! ollama list | grep -q "${MODEL%%:*}"; then
  echo "Pulling model $MODEL (one-time download, ~2 GB)..."
  ollama pull "$MODEL"
else
  echo "Model already present: $MODEL"
fi

# Create required data directories
mkdir -p data/documents data/chroma_db logs

echo ""
echo "Setup complete."
echo ""
echo "Next steps:"
echo "  1. Add your library documents to data/documents/ (see IMPLEMENTATION_PLAN.md)"
echo "  2. Run the indexer:  PYTHONPATH=. python -m backend.app.rag.indexer"
echo "  3. Start the app:    ./run.sh"
echo ""
echo "Open http://127.0.0.1:8000 once the app is running."
