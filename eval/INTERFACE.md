# Shared interface (v0.1)

Owner: claude-guanyu (`eval/`). Code: [`eval/schema.py`](schema.py), stdlib only, importable from `app/` and `pipeline/`. It starts from claude-zhihao's draft in message 008; the changes are listed at the end.

## Pipeline contract

A pipeline is a callable `(item: EvalItem, image: PIL.Image) -> PipelineResult`. The app can call the same function with a bare question by building an `EvalItem` with no gold fields.

```json
{
  "answer": "string | null",           // null = abstained
  "abstained": false,
  "evidence_boxes": [{"page": 0, "box": [x0, y0, x1, y1], "source": "ocr|native_text|overview|zoom|full_image|gold_crop|model_box", "label": null}],
  "route": [{"step": "index|ocr|native_text|route|overview|zoom|answer|fallback|abstain", "target": "B3|null", "box": [..]|null, "note": null}],
  "usage": [{"step_index": 0, "provider": "anthropic", "model": "claude-opus-5-5",
             "input_text_tokens": 0, "input_image_tokens": 0, "output_tokens": 0,
             "cache_read_tokens": 0, "cache_write_tokens": 0,
             "latency_ms": 0, "cost_usd": 0.0, "estimated": false,
             "image_px": [[w, h]], "retry": false, "note": null}],
  "pipeline": "full_image_cached", "question_id": "…", "image_id": "…", "error": null, "schema_version": "0.1"
}
```

## Rules

1. **Coordinates.** Every box (evidence and route) is `[x0, y0, x1, y1]` normalized to 0–1 on the **original** image, origin top-left. Pipelines that answer from a crop map the box back before returning.
2. **One `usage` record per API call**, including indexing, routing, retries, fallbacks and failed zooms. The overview and routing calls are charged even when the zoom fails (006).
3. **`model` is the model that actually served the call**, after any server-side fallback, so the price matches.
4. **`estimated: true`** whenever a token or cost number does not come from the provider's response.
5. **`image_px`** lists the pixel sizes actually sent, so the billing check can tie tokens to pixels.
6. **Cache read and write are separate.** On Anthropic, writes cost 1.25× input and reads 0.1× (`eval/pricing.py`).
7. **Errors are results.** A failed call sets `error`; it is not raised past the pipeline.
8. **Abstention.** Unanswerable items expect `abstained: true`. A refusal counts as abstention and is noted in `error`.

## Changes from the 008 draft

- `cached_tokens` split into `cache_read_tokens` and `cache_write_tokens`.
- `image_px`, `retry` and `note` added to usage; `pipeline`, `question_id`, `image_id`, `error` and `schema_version` added at the top level.
- More step kinds (`index`, `native_text`, `route`, `abstain`) and evidence sources.
- `route.box` uses the same convention as `evidence_boxes`.
- The dataset record (`EvalItem`, gold labels, evidence type, answerable, pair id) is separate: see [`data/README.md`](data/README.md).

Changes to field names: propose in a message; bump `SCHEMA_VERSION`.
