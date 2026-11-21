# Live model run: Qwen2.5-VL-7B-Instruct (local vLLM on RCP), 36 visual questions, $0

- Who / when: claude-zhihao, 2026-11-21, master at the commit that adds this file
- Backend: `local:Qwen/Qwen2.5-VL-7B-Instruct`, vLLM v0.11.0, 1 GPU on RCP (job `lh-vlm-qwen7b`), temperature 0
- Items: the 36 `evidence_type == visual` items of `eval/data/accident_statement` (q4 B's ticks, q5 "did A tick 8", q6 sketch), 12 forms
- This is the first **model** measurement in the repo. Accuracy is MEASURED; tokens are what vLLM reported; cost is $0 (local GPU).

| pipeline | q4 ticks | q5 tick yes/no | q6 sketch | all | zoomed | input tok/q |
|---|---|---|---|---|---|---|
| full page | 4/12 | 11/12 | 0/12 | **42%** | – | 2120 |
| gold crop 384 px (oracle region) | 7/12 | 12/12 | 5/12 | **67%** | 36/36 | 563 |
| `pipeline.visual:factory` | 3/12 | 12/12 | 0/12 | **42%** | **0/36** | 609 |
| `pipeline.visual:factory_force_zoom` | 0/12 | 0/12 | 9/12 | **25–28%** | 24/36 | 778 |

## Reading

1. **A good crop helps this model** (42% → 67%, at ~1/4 of the input tokens). The premise of zooming holds for a 7B VLM.
2. **The model never asks to zoom** when allowed to answer from the overview: it answers from a 434×536 thumbnail and is overconfident. So the default route equals the full page here, at ~29% of its input tokens.
3. **Region selection is the bottleneck.** Forced to zoom, it finds the sketch (q6: 9/12, better than the gold 384-px crop, because it takes the whole panel) but fails the narrow tick column (q4: 0/12, often replying with row labels instead of cells) and the A-column tick (q5: 0/12, picks the page middle and abstains).
4. **Evidence boxes:** Qwen2.5-VL returns boxes in absolute pixels; `pipeline.visual` now normalizes them (`normalize_box`). It rarely returns a box at all under our prompt, so evidence hit stays ~0. `eval/pipelines/baselines.py` has the same pixel-box issue (claude-guanyu's file).

## Implication

For a weak local model, "let the model pick the region" does not work yet. Cheaper routes to the right crop: OCR-anchored selection (the OCR route already knows where "12. CIRCUMSTANCES" and column B are), a form template, or a stronger model only for the overview call. The 67% gold-crop ceiling vs 42% full page is the gap a good selector can win.

Raw harness report of the same run follows.

---

### Run 2026-11-21T15:25:41+0100 · commit `c64574c` · `/private/tmp/claude-501/-Users-zhihaochen--claude-spares-spare-nEMrsO/bb19789b-80c3-4426-9b14-8a9a8efdf7a2/scratchpad/visual_items.jsonl` · input `clean` · spent $0.0000

| pipeline | group | n | acc | joint | hit@0.3 | abstain | correct abstain | $/q | p50 ms | img tok/q | txt tok/q | out tok/q | calls/q | pair follow |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `full_image@local:Qwen/Qwen2.5-VL-7B-Instruct` | all | 36 | 42% | 0% | 0% | 0% | – | 0.00000 | 125 | 0 | 2120 | 7 | 1.00 | 0% |
| `full_image@local:Qwen/Qwen2.5-VL-7B-Instruct` | visual | 36 | 42% | 0% | 0% | 0% | – | 0.00000 | 125 | 0 | 2120 | 7 | 1.00 |  |
| `gold_crop_px:384@local:Qwen/Qwen2.5-VL-7B-Instruct` | all | 36 | 67% | 0% | 0% | 0% | – | 0.00000 | 496 | 0 | 563 | 23 | 1.00 | 0% |
| `gold_crop_px:384@local:Qwen/Qwen2.5-VL-7B-Instruct` | visual | 36 | 67% | 0% | 0% | 0% | – | 0.00000 | 496 | 0 | 563 | 23 | 1.00 |  |
| `pipeline.visual:factory` | all | 36 | 42% | 0% | 0% | 0% | – | 0.00000 | 613 | 0 | 609 | 46 | 1.00 | 0% |
| `pipeline.visual:factory` | visual | 36 | 42% | 0% | 0% | 0% | – | 0.00000 | 613 | 0 | 609 | 46 | 1.00 |  |
| `pipeline.visual:factory_force_zoom` | all | 36 | 25% | 0% | 0% | 36% | – | 0.00000 | 1034 | 0 | 778 | 54 | 1.67 | 0% |
| `pipeline.visual:factory_force_zoom` | visual | 36 | 25% | 0% | 0% | 36% | – | 0.00000 | 1034 | 0 | 778 | 54 | 1.67 |  |

`*` = contains estimated usage. Cost per question excludes one-off indexing unless the pipeline recorded it in `usage`.
