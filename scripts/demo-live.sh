#!/usr/bin/env bash
# LIVE demo on the presenting Mac: local OCR + real model calls on the crop (or the page), billed via OpenRouter.
# Needs OPENROUTER_API_KEY in the environment or in a git-ignored .env at the repository root (never commit it).
# A failed live call falls back to the labelled fixture replay (DEMO_REPLAY=1); new live calls stop once a per-server spend threshold is reached.
# Usage: ./scripts/demo-live.sh [port]
#   env: EVAL_MODEL (default or:anthropic/claude-haiku-5.5), APP_LIVE_MAX_USD (default 1.00)
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8000}"
bash scripts/prepare-demo.sh
if [ -z "${OPENROUTER_API_KEY:-}" ] && [ -f .env ]; then
  set -a; . ./.env; set +a
fi
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "OPENROUTER_API_KEY not set (environment or .env). Use ./scripts/demo.sh for the key-free demo."
  exit 1
fi
# python.org Python on macOS ships without root certificates: use certifi's bundle for HTTPS.
if [ -z "${SSL_CERT_FILE:-}" ]; then
  SSL_CERT_FILE="$(.venv/bin/python -m certifi)"
  export SSL_CERT_FILE
fi
export EVAL_MODEL="${EVAL_MODEL:-or:anthropic/claude-haiku-5.5}"
# If Ollama runs on this Mac with the local model, offer it too: the presenter switches cloud <-> on-device in the app.
# Start Ollama with OLLAMA_CONTEXT_LENGTH=8192 so whole-page "Compare" calls fit (default 4096 only fits crops and text).
LOCAL_VLM="${LOCAL_VLM:-qwen2.5vl:7b}"
if [ -z "${APP_MODELS:-}" ] && curl -s -m 2 http://localhost:11434/api/tags 2>/dev/null | grep -q "\"$LOCAL_VLM\""; then
  export APP_MODELS="$EVAL_MODEL,local:$LOCAL_VLM" OPENAI_BASE_URL="${OPENAI_BASE_URL:-http://localhost:11434/v1}"
  echo "Ollama found: the app can also answer with $LOCAL_VLM on this laptop (model picker, top right)."
fi
echo "Evidence Zoom LIVE demo on http://localhost:${PORT}  (model ${EVAL_MODEL}, live spend stop threshold \$${APP_LIVE_MAX_USD:-1.00}; replay only if a live call fails)"
PIPELINE=pipeline.router DEMO_LIVE=1 DEMO_REPLAY=1 exec .venv/bin/uvicorn app.server:app --port "$PORT"
