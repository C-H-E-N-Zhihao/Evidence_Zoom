# LN head (Qwen2.5-VL-3B, layer 9, LNdoc head) as the pointer in `pipeline.pointer` (POINTER_SOURCE=file), run by claude-zhihao

Regions: `regions_receipts_v1_L9.json` (241), `regions_realdocs_v2_L9.json` (121 DocVQA + InfographicVQA with images), from `run.py infer` at b1588bc. Layer 9 was the
first trained layer. The val-selected layer is pending (other layers retraining). Pointer evals at master f74edea, readers Qwen 7B / 72B (vLLM), $0.

| set | reader | **LN-head pointer** ANLS (tok/q) | Qwen-grounding pointer ANLS (tok/q) | shipping route ANLS (tok/q) |
|---|---|---|---|---|
| receipts_v1 (241) | 7B | **0.807** (1071) | 0.782 (1374) | 0.851 (704) |
| receipts_v1 (241) | 72B | **0.888** (1122) | 0.873 (1390) | 0.938 (724) |
| realdocs_v2 DocVQA (65) | 7B / 72B | **0.862 / 0.882** | 0.784 / 0.776 | 0.930 / 0.934 |
| realdocs_v2 InfographicVQA (56) | 7B / 72B | **0.630 / 0.713** | 0.511 / 0.676 | 0.657 / 0.730 |

Region coverage on receipts_v1 gold boxes (121 with boxes): top-4 cells' rectangle contains every gold centre 42 % at 0.20 page area (random top-4: 65 % at 0.43);
per unit area ≈ 1.5× random. **Reading:** the frozen-feature phrase→location head is a **better pointer than Qwen-7B's own grounding** (higher ANLS at fewer tokens on every set),
but still below the shipping route, which uses no pointer at all. Exploratory; one run; layer 9 only.
