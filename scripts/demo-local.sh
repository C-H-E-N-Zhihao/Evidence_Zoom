#!/usr/bin/env bash
# ON-DEVICE demo: local OCR + a small vision model running on this Mac through Ollama. No API key, $0 per call,
# the document never leaves the machine. Falls back to the labelled fixture replay if a model call fails.
# Setup once: brew install ollama && ollama serve (separate terminal) && ollama pull qwen2.5vl:7b
# Usage: ./scripts/demo-local.sh [port]     env: LOCAL_VLM (default qwen2.5vl:7b), OLLAMA_URL (default http://localhost:11434)
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8000}"
MODEL="${LOCAL_VLM:-qwen2.5vl:7b}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
bash scripts/prepare-demo.sh
if ! curl -s -m 3 "$OLLAMA_URL/api/tags" >/dev/null; then
  echo "Ollama is not running at $OLLAMA_URL. Start it with: ollama serve"
  exit 1
fi
if ! curl -s -m 3 "$OLLAMA_URL/api/tags" | grep -q "\"$MODEL\""; then
  echo "Model $MODEL not found in Ollama. Pull it with: ollama pull $MODEL"
  exit 1
fi
export EVAL_MODEL="local:$MODEL" OPENAI_BASE_URL="$OLLAMA_URL/v1"
echo "Evidence Zoom ON-DEVICE demo on http://localhost:${PORT}  (model $MODEL via Ollama; no API key; replay only if a call fails)"
PIPELINE=pipeline.router DEMO_LIVE=1 DEMO_REPLAY=1 exec .venv/bin/uvicorn app.server:app --port "$PORT"
