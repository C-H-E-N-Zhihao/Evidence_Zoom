#!/usr/bin/env bash
# LIVE demo on the presenting Mac: local OCR + real model calls on the crop (or the page), billed via OpenRouter.
# Needs OPENROUTER_API_KEY in the environment or in a git-ignored .env at the repository root (never commit it).
# A failed live call falls back to the labelled fixture replay (DEMO_REPLAY=1); live spend is capped per server run.
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
echo "Evidence Zoom LIVE demo on http://localhost:${PORT}  (model ${EVAL_MODEL}, live spend cap \$${APP_LIVE_MAX_USD:-1.00}; replay only if a live call fails)"
PIPELINE=pipeline.router DEMO_LIVE=1 DEMO_REPLAY=1 exec .venv/bin/uvicorn app.server:app --port "$PORT"
