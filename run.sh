#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH:-.}"
PYTHON="${VENV_PYTHON:-/Users/saad/Desktop/Python/Virtual/venv/bin/python}"

# shellcheck source=scripts/ollama_runtime.sh
source "./scripts/ollama_runtime.sh"

cleanup() {
  ollama_runtime_stop
}
trap cleanup EXIT INT TERM

if ! ollama_runtime_start; then
  exit 1
fi

# Do not use exec here: we need the EXIT trap to stop managed Ollama.
"$PYTHON" -m uvicorn backend.app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --reload
