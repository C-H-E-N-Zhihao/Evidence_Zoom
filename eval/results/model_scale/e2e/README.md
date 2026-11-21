# End to end, development layout (all 96 questions), pipeline code at b42ece9 (before 055's q5 note)

`experiments/model_scale/run_e2e.sh`: OCR answer → OCR-anchored crop → overview fallback
(`cascade:fn:pipeline.ocr:answer|pipeline.anchor:factory_then_overview`) vs. the full page, local vLLM on RCP, $0.

| model | route (OCR → anchor → overview) | full page |
|---|---:|---:|
| Qwen2.5-VL-7B | **79/96 (82%)** | 75/96 (78%) |
| Qwen2.5-VL-72B-AWQ | **95/96 (99%)** | 80/96 (83%) |

This is the development layout: the anchor and OCR rules were written while looking at these forms. The
generalisation check is the held-out layout v2 (`../e2e_heldout_v2/`), run from tag `freeze-anchor-ocr-v1`.
Raw: `run_20261121-160458.json` (7B), `run_20261121-160810.json` (72B).
