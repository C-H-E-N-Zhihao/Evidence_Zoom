#!/usr/bin/env bash
# Run from the repository root. Shared by demo.sh and test.sh.
set -euo pipefail
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
