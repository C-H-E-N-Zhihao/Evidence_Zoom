# eval/: Evidence Zoom harness

Owner: claude-guanyu. Interface: [INTERFACE.md](INTERFACE.md). Data format: [data/README.md](data/README.md).

**Status:** v0.1 is written but **not yet executed**; Guanyu's machine is a shared cluster login node where nothing may run. The first person to run it, please report errors in a message.

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
```

| Pipeline | What it is |
|---|---|
| `mock` | Returns the gold label; tests the harness and app with no API call |
| `full_image` / `full_image_cached` | Full image per question; the cached variant marks the image for prompt caching (fair repeated-question baseline, 007 §2) |
| `lowres512`, `lowres256` | Fixed low-resolution overview only |
| `gold_crop`, `gold_crop_tight` | Gold evidence box cropped from original pixels at native size (5 % / 0 % margin): the upper bound for any zoom policy |
| `module:factory` | Any external pipeline, e.g. the OCR path or router in `pipeline/` |

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
