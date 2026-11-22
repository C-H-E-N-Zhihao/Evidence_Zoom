# receipts_v2 (held-out CORD-v2 validation, 248 q): the app as shipped vs the original photo, open models ($0)

Run by claude-zhihao on RCP (messages 217/218/221). Master **f74edea** (tree c17cd54e8315, clean). App defaults:
`REDACT_PII=1 OCR_FIELDS=1 GENERAL_LADDER=1 VISION_CACHE=0 LADDER_ABSENT_STOP=1 pipeline.router:factory` vs `full_image@local:…`. Qwen2.5-VL-7B-Instruct and
72B-AWQ via vLLM v0.11.0 (`local:`, temperature 0). All 248 items; images copied from claude-guanyu's RCP folder, **60/60 match `images.sha256`** (digest da1d2263f0fc9ff3).

| model | arm | substring /248 | ANLS | relaxed /248 | input tok/q | kpx/q | p50 s |
|---|---|---:|---:|---:|---:|---:|---:|
| 7B | app defaults | 217 | 0.876 | 214 | **611** | 291 | 0.5 |
| 7B | original photo | 232 | **0.934** | 230 | 1536 | 1415 | 0.8 |
| 72B | app defaults | 235 | 0.954 | 233 | **699** | 337 | 1.7 |
| 72B | original photo | 241 | **0.977** | 240 | 1536 | 1415 | 1.0 |

**Reading:** on unseen receipts the shipped route uses **40 % (7B) / 46 % (72B) of the photo's input tokens** and loses 0.058 / 0.023 ANLS with these open models.
Token-per-correct scoring via `eval.token_table` is left to claude-guanyu (221). Compare with claude-andrew-b's Haiku pair on the same set. One run.
