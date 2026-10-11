#!/usr/bin/env bash
# Start Ollama only when needed; stop it on app exit if this script started it.
# If Ollama was already running (e.g. brew services), leave it running.

ollama_reachable() {
  curl -sf --max-time 2 "${OLLAMA_BASE_URL:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1
}

ollama_runtime_start() {
  OLLAMA_MANAGED_BY_APP=0
  MANAGED_OLLAMA_PID=""

  if [[ "${MANAGE_OLLAMA:-1}" == "0" ]]; then
    if ! ollama_reachable; then
      echo "Ollama is not reachable and MANAGE_OLLAMA=0."
      echo "Start it with: brew services start ollama"
      return 1
    fi
    echo "Using existing Ollama (MANAGE_OLLAMA=0)."
    return 0
  fi

  if ollama_reachable; then
    echo "Ollama already running. It will stay up after you stop the app."
    return 0
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama is not installed. Run: brew install ollama && ./setup.sh"
    return 1
  fi

  local log_file="${OLLAMA_LOG:-.ollama-runtime.log}"
  echo "Starting Ollama for this app session (log: ${log_file})..."
  OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}" OLLAMA_PORT="${OLLAMA_PORT:-11434}" \
    ollama serve >>"${log_file}" 2>&1 &
  MANAGED_OLLAMA_PID=$!
  OLLAMA_MANAGED_BY_APP=1

  local attempt=1
  while (( attempt <= 45 )); do
    if ollama_reachable; then
      echo "Ollama is ready."
      return 0
    fi
    if ! kill -0 "${MANAGED_OLLAMA_PID}" 2>/dev/null; then
      echo "Ollama exited during startup. See ${log_file}"
      return 1
    fi
    sleep 1
    attempt=$((attempt + 1))
  done

  echo "Timed out waiting for Ollama. See ${log_file}"
  ollama_runtime_stop
  return 1
}

ollama_runtime_stop() {
  if [[ "${OLLAMA_MANAGED_BY_APP:-0}" != "1" || -z "${MANAGED_OLLAMA_PID:-}" ]]; then
    return 0
  fi
  echo "Stopping Ollama (started by this app)..."
  kill "${MANAGED_OLLAMA_PID}" 2>/dev/null || true
  wait "${MANAGED_OLLAMA_PID}" 2>/dev/null || true
  MANAGED_OLLAMA_PID=""
  OLLAMA_MANAGED_BY_APP=0
}
