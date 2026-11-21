#!/usr/bin/env bash
# First paid sweep, as agreed in messages 017 / 022 / 026 / 039. One command for whoever holds the key.
#
#   CHEAP=or:<cheap vision model id> STRONG=or:<strong vision model id> OPENROUTER_API_KEY=... \
#       ./eval/first_paid_sweep.sh [budget_usd_per_step, default 1.00]
#
#   (Anthropic instead: CHEAP=claude-haiku-5-5 STRONG=claude-opus-5-5 ANTHROPIC_API_KEY=...;
#    then step 0 also measures image billing with the free count_tokens endpoint.)
#
# Needs macOS for live OCR (ROUTER_REQUIRE_OCR=1 makes it fail loudly otherwise). Every step has its own hard
# --max-cost cap; the worst case is 5 x budget. Outputs go to eval/results/paid_<timestamp>/ (REPORT.md + PNGs);
# commit that folder's .md and .png files, not the raw JSON, unless the team wants it.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CHEAP:?set CHEAP to a model string, e.g. or:<id> or claude-haiku-5-5}"
: "${STRONG:?set STRONG to a model string}"
BUDGET=${1:-1.00}
PY=${PY:-.venv/bin/python}
[ -x "$PY" ] || PY=python3
I=eval/data/accident_statement/items.jsonl
OUT=eval/results/paid_$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"
export ROUTER_REQUIRE_OCR=1
run() { echo; echo "== $1"; shift; "$@"; }

# 0. free checks first: harness sanity, and (Anthropic only) how images are billed
run "0a eval selftest (free)" $PY -m eval.selftest
if [[ "$CHEAP" == claude-* || "$STRONG" == claude-* ]]; then
  run "0b billing probe (free count_tokens)" $PY -m eval.billing_probe --image app/static/sample.png --out "$OUT/billing_probe.json"
fi
[ -f "$I" ] || $PY -m eval.data.accident_statement.generate

# 1. controls on the cheap model + the strong full page: what does each input cost and earn?
run "1 controls, clean" $PY -m eval.run_eval --items "$I" --out "$OUT" --max-cost "$BUDGET" --pipelines \
  "full_image@$CHEAP" "full_image_cached@$CHEAP" "full_image_cached@$STRONG" \
  "lowres:768@$CHEAP" "gold_crop_px:384@$CHEAP" "overview_gold:512:384@$CHEAP"

# 2. the product routes end to end (OCR first), cheap model on the visual stage
run "2 routes, clean" env EVAL_MODEL="$CHEAP" $PY -m eval.run_eval --items "$I" --out "$OUT" --max-cost "$BUDGET" \
  --pipelines pipeline.router:factory pipeline.router:factory_anchor pipeline.anchor:factory_then_overview \
  "cascade:fn:pipeline.ocr:answer|cascade:checkbox_pixels|pipeline.anchor:factory_then_overview"

# 3. the same routes on phone-photo inputs, against the strong cached page
run "3 routes, phone photo" env EVAL_MODEL="$CHEAP" $PY -m eval.run_eval --items "$I" --out "$OUT" \
  --max-cost "$BUDGET" --degrade phone_photo \
  --pipelines pipeline.router:factory pipeline.router:factory_anchor "full_image_cached@$STRONG"

# 4. does the answer depend on the cited region? (subset)
run "4 reliance, cheap full page" env EVAL_MODEL="$CHEAP" $PY -m eval.reliance --items "$I" --pipeline full_image \
  --limit 24 --max-cost "$BUDGET" --out "$OUT"

# 5. reports and charts
runs=$(ls "$OUT"/run_*.json)
run "5a report" $PY -m eval.report $runs --out "$OUT/REPORT.md"
for g in all visual; do
  for x in usd tokens; do
    $PY -m eval.plot_frontier $runs --group $g --x $x --out "$OUT/frontier_${g}_${x}.png" || true
  done
done
for r in $runs; do $PY -m eval.plot_cost_curve "$r" --out "${r%.json}_cost_curve.png" || true; done
echo; echo "done: $OUT  (commit REPORT.md and the PNGs; post a message with the spend from each run's meta.spent_usd)"
