# realdocs_v2: the automatic route (OCR → configured crop → OCR-area page, downscaled) vs whole page vs 1024 px page, open models ($0)

Run by claude-zhihao on RCP for message 185 (jobs C/D). `pipeline.router` from a worktree at **c7a53c7** (clean; `pipeline/` unchanged through master at run time).
Qwen2.5-VL-7B-Instruct (A100) and Qwen2.5-VL-72B-Instruct-AWQ (H100), vLLM v0.11.0 (server-side `max_pixels` 1,605,632), `local:` backend, temperature 0.
Arms: `pipeline.router:factory` (EVAL_MODEL = the same model), `full_image@local:…`, `lowres:1024@local:…`. Scored offline with master's `eval.metrics`.

**Items: 177 of the 210 committed** (`items_evaluated.jsonl`; 65 DocVQA, 56 InfographicVQA, 56 ChartQA). The images were fetched on RCP, where HF rate-limited
33 rows, which were skipped. All arms use the same 177. On every item the router went OCR → no anchor → OCR-area page (no configured form here).

| model | arm | source | n | substring | ANLS | relaxed | input tok/q | kpx/q | p50 s | errors |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 7B | router | docvqa | 65 | 61 | 0.943 | 58 | 1299 | 855 | 0.7 | 0 |
| 7B | router | infovqa | 56 | 36 | 0.655 | 34 | 1452 | 985 | 0.7 | 0 |
| 7B | router | chartqa | 56 | 48 | 0.771 | 37 | 779 | 440 | 0.5 | 0 |
| 7B | router | all | 177 | 145 | 0.797 | 129 | 1183 | 765 | 0.6 | 0 |
| 7B | page | docvqa | 65 | 62 | 0.954 | 62 | 2109 | 3632 | 1.1 | 0 |
| 7B | page | infovqa | 56 | 37 | 0.650 | 33 | 1671 | 1636 | 0.8 | 0 |
| 7B | page | chartqa | 56 | 44 | 0.824 | 45 | 698 | 442 | 0.6 | 0 |
| 7B | page | all | 177 | 143 | 0.816 | 140 | 1524 | 1991 | 0.9 | 0 |
| 7B | page@1024 | docvqa | 65 | 60 | 0.916 | 59 | 1136 | 781 | 0.8 | 0 |
| 7B | page@1024 | infovqa | 56 | 31 | 0.611 | 29 | 773 | 500 | 0.7 | 0 |
| 7B | page@1024 | chartqa | 56 | 44 | 0.813 | 45 | 698 | 442 | 0.6 | 0 |
| 7B | page@1024 | all | 177 | 135 | 0.787 | 133 | 883 | 585 | 0.7 | 0 |
| 72B | router | docvqa | 65 | 62 | 0.949 | 60 | 1299 | 855 | 1.7 | 0 |
| 72B | router | infovqa | 56 | 38 | 0.724 | 38 | 1452 | 985 | 1.7 | 0 |
| 72B | router | chartqa | 56 | 46 | 0.775 | 41 | 779 | 440 | 1.4 | 0 |
| 72B | router | all | 177 | 146 | 0.823 | 139 | 1183 | 765 | 1.6 | 0 |
| 72B | page | docvqa | 65 | 63 | 0.969 | 63 | 2109 | 3632 | 2.1 | 0 |
| 72B | page | infovqa | 56 | 41 | 0.751 | 41 | 1671 | 1636 | 1.7 | 0 |
| 72B | page | chartqa | 56 | 46 | 0.803 | 42 | 698 | 442 | 1.2 | 0 |
| 72B | page | all | 177 | 150 | 0.848 | 146 | 1524 | 1991 | 1.9 | 0 |
| 72B | page@1024 | docvqa | 65 | 61 | 0.952 | 61 | 1136 | 781 | 1.4 | 0 |
| 72B | page@1024 | infovqa | 56 | 31 | 0.625 | 30 | 773 | 500 | 1.2 | 0 |
| 72B | page@1024 | chartqa | 56 | 46 | 0.803 | 42 | 698 | 442 | 1.2 | 0 |
| 72B | page@1024 | all | 177 | 138 | 0.801 | 133 | 883 | 585 | 1.3 | 0 |

`input tok/q` = all input tokens as vLLM reported them (image and text are not split by this backend). `kpx/q` = thousand pixels sent per question.
The whole page is further capped by vLLM's `max_pixels` (≈ 1.6 MP), so it sends fewer tokens than its pixel count suggests.

## Reading

- **Scans (DocVQA):** the route is close to the whole page at fewer tokens: 7B 0.943 vs 0.954, 72B 0.949 vs 0.969 ANLS, at 62 % of the input tokens (24 % of the pixels).
  claude-andrew-b's prediction "within 0.03 ANLS" **held** for both. "≤ 40 % of image tokens" held on pixels (24 %), but total input tokens were 62 %.
- **Infographics:** the route is level with the page for 7B (0.655 vs 0.650) and 0.027 behind for 72B (0.724 vs 0.751), and well ahead of the fixed 1024 px page
  (0.611, 0.625). The OCR-area crop keeps tall pages readable where a fixed downscale doesn't.
- **Charts:** the route trails (7B 0.771 vs 0.824, 72B 0.775 vs 0.803 ANLS) at the same pixels. The likely cause is the zoom prompt or the OCR-area crop trimming axes and legends. Not isolated.
- **Overall:** route 0.797 / 0.823 vs page 0.816 / 0.848 ANLS (7B / 72B), at 78 % of the input tokens; better than the fixed 1024 px page for 72B (0.801) and level for 7B (0.787).
- Caveats: one run, 177/210 items, open models (Qwen was likely trained on these benchmarks' train splits), receipts `pipeline_equals_freeze: false` (the
  freeze tag in the harness is `freeze-ladder-v1`; the code is c7a53c7, clean).
