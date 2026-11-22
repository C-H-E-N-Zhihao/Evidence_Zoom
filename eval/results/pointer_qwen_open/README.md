# `pipeline.pointer` with the Qwen-7B grounding pointer vs the shipping route, open models ($0)

Run by claude-zhihao on RCP (message 209). Master **b04b251** (tree ee02d3207978, clean). `POINTER_SOURCE=qwen`, `POINTER_MODEL=local:Qwen/Qwen2.5-VL-7B-Instruct`
(vLLM, low-res text-area crop → box), reader = `EVAL_MODEL` (Qwen 7B or 72B-AWQ). If the zoomed answer isn't printed in the OCR text, it falls back to the page ladder.
Same items as `receipts_v1_open/` (241) and `realdocs_v2_router_open/` (177). Compared against the router (ladder) at the same commit.

| set | reader | pointer ANLS | route (ladder) ANLS | pointer input tok/q | route input tok/q | pointer crop accepted |
|---|---|---:|---:|---:|---:|---:|
| receipts_v1 (241) | 7B | 0.782 | **0.851** | 1374 | **704** | 69/241 |
| receipts_v1 (241) | 72B | 0.873 | **0.938** | 1390 | **724** | 72/241 |
| realdocs_v2 (177) | 7B | 0.671 | **0.787** | 1871 | **1122** | 38/177 |
| realdocs_v2 (177) | 72B | 0.734 | **0.822** | 1757 | **1069** | 47/177 |

**Reading:** with these models the grounding pointer is **worse and more expensive** than the shipping route on both sets. Its crop passed the OCR check on only
21–30 % of questions; the rest paid for the pointer and zoom calls and then fell back to the ladder. Don't ship it (it's already off by default). One run per arm.
