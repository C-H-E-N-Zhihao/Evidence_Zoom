#!/usr/bin/env bash
# Key-free judge rehearsal: real OCR (Apple Vision, macOS) + visual route REPLAYED from fixture labels.
# Usage: ./scripts/demo.sh [port]      then open http://localhost:<port>
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8000}"
bash scripts/prepare-demo.sh
echo "Evidence Zoom rehearsal on http://localhost:${PORT}  (local OCR when available, visual = fixture REPLAY)"
PIPELINE=pipeline.router DEMO_REPLAY=1 DEMO_LIVE=0 exec .venv/bin/uvicorn app.server:app --port "$PORT"
