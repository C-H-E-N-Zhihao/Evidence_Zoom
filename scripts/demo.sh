#!/usr/bin/env bash
# Key-free judge rehearsal: real OCR (Apple Vision, macOS) + visual route REPLAYED from fixture labels.
# Usage: ./scripts/demo.sh [port]      then open http://localhost:<port>
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8000}"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
requirements=$(cksum app/requirements.txt eval/requirements.txt)
stamp=.venv/.demo-requirements
if [[ ! -f "$stamp" || "$(<"$stamp")" != "$requirements" ]]; then
  .venv/bin/python -m pip install -q -r app/requirements.txt -r eval/requirements.txt
  printf '%s\n' "$requirements" > "$stamp"
fi
[ -f eval/data/accident_statement/items.jsonl ] || .venv/bin/python -m eval.data.accident_statement.generate
[ -f app/static/sample.png ] || .venv/bin/python -m app.make_sample
echo "Evidence Zoom rehearsal on http://localhost:${PORT}  (local OCR when available, visual = fixture REPLAY)"
PIPELINE=pipeline.router DEMO_REPLAY=1 exec .venv/bin/uvicorn app.server:app --port "$PORT"
