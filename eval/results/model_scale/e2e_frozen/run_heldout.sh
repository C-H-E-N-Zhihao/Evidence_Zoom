#!/usr/bin/env bash
# Held-out check from tag freeze-anchor-ocr-v1 (0b2a138). Local vLLM on RCP via tunnels :8001/:8002. $0.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
S=local:Qwen/Qwen2.5-VL-7B-Instruct
L=local:Qwen/Qwen2.5-VL-72B-Instruct-AWQ
OUT=${OUT:?}
CHAIN="cascade:fn:pipeline.ocr:answer|pipeline.anchor:factory_then_overview"
$PY ops/model_proxy.py --port 8100 --route Qwen/Qwen2.5-VL-7B-Instruct=http://localhost:8001 \
    --route Qwen/Qwen2.5-VL-72B-Instruct-AWQ=http://localhost:8002 & PROXY=$!
trap 'kill $PROXY' EXIT
sleep 1
export OPENAI_BASE_URL=http://localhost:8100/v1
for M in $S $L; do
  EVAL_MODEL=$M $PY -m eval.run_eval --items eval/data/accident_statement_v2/items.jsonl --max-cost 0.01 \
      --out $OUT/heldout_v2 --pipelines "$CHAIN" "full_image@$M"
  EVAL_MODEL=$M $PY -m eval.run_eval --items eval/data/accident_statement/items.jsonl --max-cost 0.01 \
      --out $OUT/dev_v1 --pipelines "$CHAIN"
done
