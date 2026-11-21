# eval/: Evidence Zoom harness

Owner: claude-guanyu. Interface: [INTERFACE.md](INTERFACE.md). Data format: [data/README.md](data/README.md).

**Status:** the mock path was run end to end by claude-zhihao on macOS (message 010, no errors). No paid run yet. Guanyu's machine is a shared cluster login node where nothing may run, so others execute; report errors in a message.

## Setup

```bash
pip install -r eval/requirements.txt
export OPENROUTER_API_KEY=...       # AXA's $10 credit; or ANTHROPIC_API_KEY; never commit keys
```

**Providers.** The model string picks the backend ([backends/__init__.py](backends/__init__.py)):

| Model string | Backend | Cost |
|---|---|---|
| `or:<openrouter model id>`, e.g. `or:google/gemini-2.5-flash` | OpenRouter (`OPENROUTER_API_KEY`) | billed cost read from the response |
| `local:<model>`, e.g. `local:Qwen/Qwen2.5-VL-7B-Instruct` | any OpenAI-compatible server, e.g. vLLM on RCP (`OPENAI_BASE_URL`) | $0, latency still counted |
| `claude-…` | Anthropic (`ANTHROPIC_API_KEY`) | from `eval/pricing.py` |

Set one default for a whole run with `EVAL_MODEL=or:…`, or per pipeline with `<name>@<model>`. The aim is to compare models on cost, e.g. a cheap model on a crop against a strong model on the full page. The billing probe currently supports Anthropic only; on other backends, read the image tokens from the first real calls.

Run everything from the repo root (`python -m eval.<module>`). Offline unit checks: `python -m eval.selftest` ($0).

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

## Realistic inputs

`--degrade <name>` runs every pipeline on degraded inputs, using the same functions as claude-andrew-b's OCR bench (`bench/ocr_robustness.py`): `phone_photo`, `scale_1024`, `scale_768`, `jpeg_q40`, `blur_1.5`, `rotate_2`, `rotate_5`, `perspective_3%`. It answers whether the route mix, and with it the cost per question, survives real phone photos. For example, OCR falling back on a photo moves items to the paid visual path. Geometric degradations make gold boxes approximate; the report says so.

```bash
python -m eval.run_eval --items eval/data/accident_statement/items.jsonl --degrade phone_photo \
    --pipelines pipeline.router:factory full_image_cached --max-cost 1.00
```

## Model-free stages

`checkbox_pixels` wraps andrew-ocr's classical checkbox reader (`experiments/checkbox_pixels.py`; needs numpy and scipy). It costs $0, its local latency is recorded, and it hands off with `fallback` when it cannot answer. A three-stage chain of OCR, then pixel ticks, then the model:

```bash
python -m eval.run_eval --items eval/data/accident_statement/items.jsonl --max-cost 0.01 --pipelines \
    "cascade:fn:pipeline.ocr:answer|cascade:checkbox_pixels|pipeline.visual:factory" pipeline.router:factory
```

## Local GPU time is not free

Self-hosted model calls (`local:` backend) record `device: "gpu"`, and reports show **GPU s/q**: wall-clock seconds per question, one request at a time, so roughly GPU time. They cost $0 by default. To price them as rented hardware, set `EVAL_GPU_USD_PER_HOUR=<rate>`; costs are then marked estimated. State the rate you used, for example a cloud on-demand price for the GPU type. CPU-local stages (OCR, checkbox_pixels) stay $0.

## The pitch chart: accuracy against cost

```bash
python -m eval.plot_frontier eval/results/model_scale/run_*.json --group visual --x tokens   # or usd | gpu_s | latency_ms
```

One point per (run, pipeline). The Pareto frontier is filled: no other point there is both cheaper and at least as accurate. Dominated points are hollow, and the title carries the commits and items. Use `--group` (`text`, `visual`, …) so OCR-answerable questions do not hide the visual result.
