# eval/: Evidence Zoom harness

Owner: claude-guanyu. Interface: [INTERFACE.md](INTERFACE.md). Data format: [data/README.md](data/README.md).

**Status:** the mock path was run end to end by claude-zhihao on macOS (message 010, no errors). No paid run yet. Guanyu's machine is a shared cluster login node where nothing may run, so others execute; report errors in a message.

## Setup

```bash
pip install -r eval/requirements.txt
export ANTHROPIC_API_KEY=...        # or a git-ignored .env; never commit it
```

Run everything from the repo root (`python -m eval.<module>`).

## 1. Billing check first (free)

```bash
python -m eval.billing_probe --image some_page.png
```

This uses the free `count_tokens` endpoint to measure image tokens for the full image, overviews, native crops, and a crop upscaled to full size (the 004 trap). It writes `eval/results/billing_probe.json`, which is committed. It decides whether overview + crop can save money on this backend.

## 2. Run the controls

```bash
python -m eval.run_eval --items eval/data/<set>/items.jsonl --pipelines mock               # no API cost
python -m eval.run_eval --items eval/data/<set>/items.jsonl \
    --pipelines full_image full_image_cached lowres512 gold_crop --limit 10 --max-cost 0.50
python -m eval.plot_cost_curve eval/results/run_<timestamp>.json
python -m eval.report eval/results/run_<timestamp>.json --out eval/results/REPORT.md   # Markdown table
```

| Pipeline | What it is |
|---|---|
| `mock` | Returns the gold label; tests the harness and app with no API call |
| `full_image` / `full_image_cached` | Full image per question; the cached variant marks the image for prompt caching (fair repeated-question baseline, 007 §2) |
| `lowres512`, `lowres256` | Fixed low-resolution overview only |
| `gold_crop`, `gold_crop_tight` | Gold evidence box cropped from original pixels at native size (5 % / 0 % margin): the upper bound for any zoom policy |
| `gold_crop_px:<side>` | Crop-budget sweep: a `side`×`side` native-pixel window centred on the gold evidence (grown if the evidence is bigger) |
| `lowres:<long_side>` | Low-resolution sweep |
| `overview_gold:<ov>:<crop>` | Overview (long side `ov`) + correct crop (`crop` px) in one call: the upper bound for the 006 policy at that budget |
| `<name>@<model>` | Same control on another model, e.g. `full_image_cached@claude-haiku-5-5` (the cheap-model competitor every zoom route must beat) |
| `fn:<module>:<attr>` | An app-style `answer(image, question)` function, e.g. `fn:pipeline.ocr:answer` |
| `cascade:<a>\|<b>` | Run `a`; if its last route step is `fallback`, run `b` and merge route and usage (a's cost always charged). E.g. `"cascade:pipeline.ocr:answer\|full_image_cached"` |
| `module:factory` | Any external pipeline factory |

Sweep example (006's first comparison, gold crop before a model-selected crop):

```bash
python -m eval.run_eval --items eval/data/<set>/items.jsonl --max-cost 1.00 --pipelines \
    full_image full_image_cached lowres:384 lowres:768 \
    gold_crop_px:192 gold_crop_px:384 gold_crop_px:768 overview_gold:384:384 overview_gold:512:384
```

All baselines share one prompt and answer format (`pipelines/baselines.py`). The default model is `claude-opus-5-5` at low effort, with server-side refusal fallback enabled; the served model is priced from the response.

## Outputs

`eval/results/run_<timestamp>.json` holds the commit, the items file, the spend, and for each pipeline:
- `summary`, overall and per evidence type: accuracy, evidence hit@0.3 and mean IoU, joint answer+evidence, abstention and correct-abstention rates, errors, cost, median latency, calls, token totals, and whether any number is estimated;
- `cost_curve`: mean cumulative cost against questions per image;
- `results`: every `PipelineResult`.

## 3. Reliance tests (does the answer depend on the cited region?)

```bash
python -m eval.reliance --items eval/data/<set>/items.jsonl --pipeline full_image --limit 10 --max-cost 0.50
```

For each answerable item, the cited box (or the gold box if none is cited) is tested three ways:
- **Sufficiency:** keep only the cited box; the answer should stay the same.
- **Necessity:** grey out the cited box; the answer should change, or the model should abstain.
- **Control:** grey out a size-matched random box; the answer should stay the same.

Rates are computed over items the base pipeline got right. The value-swap test uses counterfactual pairs (`pair_id`) and is reported as `pair_follow_rate` in every `run_eval` report.

## Not done yet

- Synthetic accident-statement generator (`eval/data/`): offered by claude-zhihao in 007/008.
- Crop-budget sweep and an LLM-judge for free-form answers.
