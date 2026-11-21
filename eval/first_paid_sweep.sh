#!/usr/bin/env bash
# First paid sweep, as agreed in messages 017 / 022 / 026 / 039, trimmed per claude-zhihao's budget proposal
# (054-claude-zhihao). One command for the key holder.
#
#   CHEAP=or:anthropic/claude-haiku-5.5 STRONG=or:anthropic/claude-sonnet-5.5 OPENROUTER_API_KEY=... \
#       SWEEP=trim ./eval/first_paid_sweep.sh [budget_usd_per_step, default 1.00]
#
#   SWEEP=trim (default): only what the free local runs could not settle (billed frontier numbers, real image
#                         billing, the shipping route on clean and phone-photo inputs). 3 paid steps.
#   SWEEP=full:           adds low-res and overview+crop controls, the model-zoom router and the reliance step.
#   Anthropic direct instead of OpenRouter: CHEAP=claude-haiku-5-5 STRONG=claude-sonnet-5-5 ANTHROPIC_API_KEY=...
#                         (step 0 then also measures image billing with the free count_tokens endpoint).
#
# Needs macOS for live OCR (ROUTER_REQUIRE_OCR=1 makes it fail loudly otherwise). Every paid step has its own hard
# --max-cost cap: worst case 3 x budget (trim) or 5 x budget (full). Output: eval/results/paid_<timestamp>/.
# Commit REPORT.md and the PNGs; post meta.spent_usd of every run.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CHEAP:?set CHEAP to a model string, e.g. or:<id> or claude-haiku-5-5}"
: "${STRONG:?set STRONG to a model string}"
SWEEP=${SWEEP:-trim}
BUDGET=${1:-1.00}
PY=${PY:-.venv/bin/python}
[ -x "$PY" ] || PY=python3
I=eval/data/accident_statement/items.jsonl
OUT=eval/results/paid_$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"
export ROUTER_REQUIRE_OCR=1
run() { echo; echo "== $1"; shift; "$@"; }
echo "sweep=$SWEEP budget/step=\$$BUDGET cheap=$CHEAP strong=$STRONG out=$OUT"

# 0. free checks first: harness sanity, and (Anthropic direct only) how images are billed
run "0a eval selftest (free)" $PY -m eval.selftest
if [[ "$CHEAP" == claude-* || "$STRONG" == claude-* ]]; then
  run "0b billing probe (free count_tokens)" $PY -m eval.billing_probe --image app/static/sample.png --out "$OUT/billing_probe.json"
fi
[ -f "$I" ] || $PY -m eval.data.accident_statement.generate

# 1. controls: strong model on the (cached) page vs cheap model on the page and on the right crop.
#    Real image billing per input size comes from these rows' billed tokens.
C1=("full_image_cached@$STRONG" "full_image@$CHEAP" "gold_crop_px:384@$CHEAP")
[ "$SWEEP" = full ] && C1+=("full_image_cached@$CHEAP" "lowres:768@$CHEAP" "overview_gold:512:384@$CHEAP")
run "1 controls, clean" $PY -m eval.run_eval --items "$I" --out "$OUT" --max-cost "$BUDGET" --pipelines "${C1[@]}"

# 2. the shipping route end to end (OCR -> anchor crop -> overview), cheap model on the visual stage
C2=(pipeline.router:factory_anchor pipeline.anchor:factory_then_overview)
[ "$SWEEP" = full ] && C2+=(pipeline.router:factory
  "cascade:fn:pipeline.ocr:answer|cascade:checkbox_pixels|pipeline.anchor:factory_then_overview")
run "2 routes, clean" env EVAL_MODEL="$CHEAP" $PY -m eval.run_eval --items "$I" --out "$OUT" --max-cost "$BUDGET" \
  --pipelines "${C2[@]}"

# 3. the shipping route on phone-photo inputs, against the strong model on the cached page
run "3 route, phone photo" env EVAL_MODEL="$CHEAP" $PY -m eval.run_eval --items "$I" --out "$OUT" \
  --max-cost "$BUDGET" --degrade phone_photo --pipelines pipeline.router:factory_anchor "full_image_cached@$STRONG"

# 4. (full only) does the answer depend on the cited region? Can also run free on the local endpoint.
if [ "$SWEEP" = full ]; then
  run "4 reliance, cheap full page" env EVAL_MODEL="$CHEAP" $PY -m eval.reliance --items "$I" --pipeline full_image \
    --limit 24 --max-cost "$BUDGET" --out "$OUT"
fi

# 5. reports and charts (free)
runs=$(ls "$OUT"/run_*.json)
run "5a report" $PY -m eval.report $runs --out "$OUT/REPORT.md"
for g in all visual; do
  for x in usd tokens; do
    $PY -m eval.plot_frontier $runs --group $g --x $x --out "$OUT/frontier_${g}_${x}.png" || true
  done
done
for r in $runs; do $PY -m eval.plot_cost_curve "$r" --out "${r%.json}_cost_curve.png" || true; done
echo; echo "done: $OUT  (commit REPORT.md and the PNGs; post the spend from each run's meta.spent_usd)"
