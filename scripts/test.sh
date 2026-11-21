#!/usr/bin/env bash
# All offline checks, $0, no API key. Usage: ./scripts/test.sh
set -uo pipefail
cd "$(dirname "$0")/.."
bash scripts/prepare-demo.sh || exit 1
PY=.venv/bin/python

fail=0
run() {  # run <title> <command...>
  echo; echo "== $1"; shift
  if "$@"; then echo "-> ok"; else echo "-> FAILED"; fail=1; fi
}
run "1/6 OCR field lookup unit checks"                      $PY -m unittest -q pipeline.ocr.test_fields
run "2/6 router unit checks (stubs)"                        $PY -m pipeline.test_router
run "3/6 visual path geometry, oracle backend, 96 items"    $PY -m pipeline.visual.selftest
run "4/6 eval harness unit checks"                          $PY -m eval.selftest
run "5/6 eval harness end to end, mock pipeline"            $PY -m eval.run_eval --items eval/data/demo_sample/items.jsonl --pipelines mock --out /tmp/evidence-zoom-test
run "6/6 demo smoke test through the app API"               $PY scripts/smoke_demo.py
echo
[ $fail -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $fail
