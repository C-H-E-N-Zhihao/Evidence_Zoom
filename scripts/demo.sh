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
# layout 3 fresh forms (images are not committed; regenerated from the committed seed, checked against images.sha256)
[ -f eval/data/accident_statement_v3b/images/eas3b-001a.png ] || EAS3_SEED=7777 EAS3_OUT=eval/data/accident_statement_v3b \
  EAS3_PREFIX=eas3b .venv/bin/python -m eval.data.accident_statement_v3.generate
echo "Evidence Zoom rehearsal on http://localhost:${PORT}  (local OCR when available, visual = fixture REPLAY)"
PIPELINE=pipeline.router DEMO_REPLAY=1 DEMO_LIVE=0 exec .venv/bin/uvicorn app.server:app --port "$PORT"
