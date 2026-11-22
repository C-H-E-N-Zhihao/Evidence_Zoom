# Learned pointers: analysis (claude-guanyu, handoff 231; corrected grid mapping)

Question: can a cheap learned "pointer" pick the evidence region, so that the model reads only a crop? Exploratory, $0 (Qwen readers on RCP vLLM, run by claude-zhihao). Scored by claude-guanyu with `eval.token_table` (`POINTER_TABLE.md`) and `eval.grid_coverage`; RCP CPU jobs.

## 1. Pointing alone: the learned pointers find the region well above chance

| pointer | set | measure | pointer | baseline |
|---|---|---|---:|---:|
| GRPO-trained Qwen2.5-VL-7B (trained on synthetic docs only) | receipts_v2, 129 gold boxes | gold centre inside the box | **0.411** | 0.093 (equal-area centre box), ≈ 0.032 (chance) |
| zero-shot Qwen2.5-VL-7B | same | same | 0.062 | 0.016 (chance) |
| LN head (frozen Qwen-3B features, layer 9) | receipts_v1, 121 gold boxes | top cell on the gold box | **0.256** | 0.066 (random) |

Sources: `rl_pointer/INDEPENDENT_SCORING.md`, `ln_pointer/INDEPENDENT_SCORING.md`. The GRPO boxes are tight: median 2.6 % of the image, and they contain the whole gold line only 4.7 % of the time.

## 2. End to end: no pointer beat the shipped route

All rows have the same questions and reader within each block. Tokens are all model tokens per correctly answered question (local GPU here).

| set (reader) | shipped route: correct / wrong / tokens | best pointer: correct / wrong / tokens | GRPO box |
|---|---|---|---|
| receipts_v2, 248, fresh (7B) | **183 / 31 / 861** | LN lines 167 / 55 / 1,282 | 143 / 75 / 2,612 |
| receipts_v2 (72B) | **183 / 13 / 1,011** | LN lines 166 / 34 / 1,443 | 139 / 62 / 2,783 |
| receipts_v1, 241, dev (7B) | **175 / 35 / 1,027** | LN box 170 / 42 / 1,651 | – |
| receipts_v1 (72B) | **174 / 18 / 1,078** | LN box 167 / 28 / 1,720 | – |
| realdocs_v2 DocVQA+Info, 121 (7B) | **97 / 24 / 1,606** | LN box 92 / 29 / 2,047 | – |
| realdocs_v2 (72B) | **99 / 22 / 1,527** | LN box 98 / 23 / 1,960 | – |

**Reading.** Every pointer variant had fewer correct answers, more wrong answers and more tokens per correct answer than the shipped route (small page first, OCR check, sharper page on a miss). Pointing better did not mean answering better: GRPO points best (section 1) but does worst end to end. Its tight crops cut the evidence. Pointer crops also often fail the OCR check and fall back to the page, which adds tokens.

**Verdict:** a research result, not a product feature. A learned pointer locates evidence far above chance, and GRPO transfers from synthetic to real receipts. But on these sets, reading a smaller whole page with an OCR check was cheaper and more accurate than any pointer crop.

**Limits:**
- one run each;
- the receipts_v2 app-route rows are at f74edea (before no-box), while the pointer runs are at 9114d53/7e3dba2;
- LN layer chosen without validation (L9; L7 for 7B);
- the GRPO boxes were not padded or snapped to lines in these runs (snapping added in 5d6e750, not measured);
- the earlier layer-9 comparisons with the wrong grid mapping (96f8233) are retired.
