#!/usr/bin/env bash
# Build and run __AGENT_NAME__ inside a Docker Sandboxes microVM.
# Requires: sbx (Docker Sandboxes) and a prior `sbx login`.
# Credentials are read from the caller's environment and never written to disk.
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX_NAME="${SANDBOX_NAME:-__AGENT_SLUG__}"
IMAGE="${IMAGE:-__AGENT_SLUG__:local}"
HOST_PORT="${HOST_PORT:-8080}"
LLM_PROVIDER="${LLM_PROVIDER:-__DEFAULT_PROVIDER__}"
LLM_MODEL="${LLM_MODEL:-__DEFAULT_MODEL__}"
export LLM_PROVIDER LLM_MODEL

case "$LLM_PROVIDER" in
  gemini) KEY_VAR=GEMINI_API_KEY ;;
  openai) KEY_VAR=OPENAI_API_KEY ;;
  anthropic) KEY_VAR=ANTHROPIC_API_KEY ;;
  ollama) KEY_VAR=OLLAMA_BASE_URL ;;
  *) echo "Unsupported LLM_PROVIDER: $LLM_PROVIDER" >&2; exit 2 ;;
esac

command -v sbx >/dev/null || { echo "sbx not found; install Docker Sandboxes" >&2; exit 1; }

if ! sbx ls 2>/dev/null | grep -Eq -- "(^|[[:space:]])${SANDBOX_NAME}([[:space:]]|$)"; then
  sbx create --name "$SANDBOX_NAME" shell "$PACKAGE_DIR:ro"
fi

sbx exec "$SANDBOX_NAME" docker version >/dev/null \
  || { echo "Docker engine unavailable inside sandbox $SANDBOX_NAME" >&2; exit 1; }

sbx exec "$SANDBOX_NAME" docker build -t "$IMAGE" "$PACKAGE_DIR"
sbx exec "$SANDBOX_NAME" docker rm -f agent >/dev/null 2>&1 || true
sbx exec -e LLM_PROVIDER -e LLM_MODEL -e "$KEY_VAR" "$SANDBOX_NAME" \
  docker run -d --name agent --restart unless-stopped \
  --read-only --tmpfs /tmp -p 8080:8080 \
  -e LLM_PROVIDER -e LLM_MODEL -e "$KEY_VAR" "$IMAGE"

sbx ports "$SANDBOX_NAME" --publish "127.0.0.1:${HOST_PORT}:8080"
echo "Agent running in microVM sandbox $SANDBOX_NAME at http://127.0.0.1:${HOST_PORT}"
echo "Stop: sbx stop $SANDBOX_NAME    Remove: sbx rm $SANDBOX_NAME"
