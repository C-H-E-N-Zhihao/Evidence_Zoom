#!/usr/bin/env bash
# All offline checks, $0, no API key. Usage: ./scripts/test.sh
set -uo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  echo "== setting up .venv (first run only)"
  python3 -m venv .venv && .venv/bin/pip install -q -r app/requirements.txt -r eval/requirements.txt || exit 1
fi
PY=.venv/bin/python
[ -f eval/data/accident_statement/items.jsonl ] || $PY -m eval.data.accident_statement.generate
[ -f app/static/sample.png ] || $PY -m app.make_sample

fail=0
run() {  # run <title> <command...>
  echo; echo "== $1"; shift
  if "$@"; then echo "-> ok"; else echo "-> FAILED"; fail=1; fi
}
run "1/4 router unit checks (stubs)"                        $PY -m pipeline.test_router
run "2/4 visual path geometry, oracle backend, 96 items"    $PY -m pipeline.visual.selftest
run "3/4 eval harness, mock pipeline, demo form"            $PY -m eval.run_eval --items eval/data/demo_sample/items.jsonl --pipelines mock --out /tmp/evidence-zoom-test
run "4/4 demo smoke test through the app API"               $PY scripts/smoke_demo.py
echo
[ $fail -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $fail
