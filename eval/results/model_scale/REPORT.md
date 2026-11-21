# Model scale × input: does a small model on the right crop match a large model on the page?

36 visual questions (12 forms × q4 B's ticks, q5 did A tick 8, q6 sketch), `eval/data/accident_statement`.
Local vLLM on RCP, temperature 0, $0. Accuracy MEASURED. Tokens as reported by vLLM. `GPU-s/q` = measured
request latency, one request at a time (7B on A100, 72B-AWQ on H100: not the same GPU type).
`TFLOPs/q` = 2 × params × tokens (prefill + decode), a hardware-neutral compute proxy (ESTIMATED).
`covers` = zoomed items whose zoom region contains ≥ 90 % of the gold evidence (`eval.metrics.zoom_coverage`).

| pipeline | model(s) | accuracy | q4 /12 | q5 /12 | q6 /12 | zoomed | covers | in tok/q | GPU-s/q | TFLOPs/q |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| `pipeline.anchor:factory` | 72B | **100%** | 12 | 12 | 12 | 36 | 36/36 | 660 | 1.61 | 103.8 |
| `gold_crop_px:384` | 72B | **94%** | 10 | 12 | 12 | 36 | 36/36 | 563 | 1.54 | 88.6 |
| `gold_crop_px:384` | 7B | **67%** | 7 | 12 | 5 | 36 | 36/36 | 563 | 0.37 | 9.7 |
| `pipeline.anchor:factory` | 7B | **61%** | 9 | 8 | 5 | 36 | 36/36 | 660 | 0.66 | 11.7 |
| `full_image` | 72B | **56%** | 7 | 12 | 1 | 0 | - | 2120 | 1.91 | 316.2 |
| `pipeline.visual:factory` | 72B | **47%** | 4 | 12 | 1 | 0 | - | 609 | 1.69 | 96.7 |
| `pipeline.visual:factory_split` | 72B | **47%** | 4 | 12 | 1 | 0 | - | 609 | 1.52 | 96.7 |
| `pipeline.visual:factory` | 7B | **42%** | 3 | 12 | 0 | 0 | - | 609 | 0.67 | 10.9 |
| `full_image` | 7B | **42%** | 4 | 11 | 0 | 0 | - | 2120 | 0.56 | 35.8 |
| `pipeline.visual:factory_force_zoom` | 72B | **31%** | 4 | 6 | 1 | 36 | 3/36 | 994 | 2.81 | 157.9 |
| `pipeline.visual:factory_force_zoom` | 7B | **28%** | 1 | 0 | 9 | 24 | 0/24 | 778 | 0.80 | 13.8 |
| `pipeline.visual:factory_split` | 72B+7B | **28%** | 2 | 7 | 1 | 36 | 3/36 | 993 | 1.88 | 86.9 |
