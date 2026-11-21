# realdocs_v1 with open-weights models on RCP: plain route, route + thumbnail, whole page ($0 provider charge)

Run by claude-zhihao (plan and predictions: message 169, committed before the runs). Qwen2.5-VL-7B-Instruct (A100) and Qwen2.5-VL-72B-Instruct-AWQ (H100),
vLLM v0.11.0, `local:` backend, temperature 0. Routes run from worktrees at the tags: **plain route** `freeze-general-v2` (tree e128edd722cc),
**route + 448 px thumbnail** `freeze-general-v3` (tree 31a3b7bb9f19, `GENERAL_THUMB_PX=448`), both `pipeline_equals_freeze: true`, clean. Whole page = `full_image`.
Scored offline from the receipts with master's `eval.metrics`: `answer_correct` (substring), `anls`, `relaxed_accuracy` (Pix2Struct, a402002).

**Items: 199 of the 200 committed** (`items_evaluated.jsonl`). The images were fetched on this Mac and each was checked against its committed `image_id`
(a hash of the decoded pixels), so the pixels are identical to claude-andrew-b's set. The PNG bytes differ (Pillow 13), digest 6ffd4d1ff813c1c3.
`rd-docvqa-374` was excluded: its re-fetched page resized to different pixels under Pillow 13 (hash mismatch).

| model | arm | source | n | substring | ANLS | relaxed | errors | no crop or page call | p50 s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 7B | route | docvqa | 99 | 78 | 0.856 | 74 | 0 | 99 | 1.0 |
| 7B | route | chartqa | 100 | 27 | 0.333 | 34 | 0 | 99 | 1.0 |
| 7B | route | all | 199 | 105 | 0.594 | 108 | 0 | 198 | 1.0 |
| 7B | page | docvqa | 99 | 90 | 0.936 | 86 | 0 | – | 1.2 |
| 7B | page | chartqa | 100 | 76 | 0.781 | 80 | 0 | – | 0.7 |
| 7B | page | all | 199 | 166 | 0.858 | 166 | 0 | – | 0.8 |
| 7B | route+thumb448 | docvqa | 99 | 89 | 0.924 | 85 | 0 | 99 | 1.2 |
| 7B | route+thumb448 | chartqa | 100 | 60 | 0.675 | 55 | 0 | 100 | 1.3 |
| 7B | route+thumb448 | all | 199 | 149 | 0.799 | 140 | 0 | 199 | 1.2 |
| 72B | route | docvqa | 99 | 82 | 0.872 | 80 | 0 | 92 | 1.9 |
| 72B | route | chartqa | 100 | 36 | 0.430 | 44 | 0 | 82 | 1.9 |
| 72B | route | all | 199 | 118 | 0.650 | 124 | 0 | 174 | 1.9 |
| 72B | page | docvqa | 99 | 92 | 0.960 | 89 | 0 | – | 2.1 |
| 72B | page | chartqa | 100 | 81 | 0.823 | 76 | 0 | – | 1.2 |
| 72B | page | all | 199 | 173 | 0.891 | 165 | 0 | – | 1.5 |
| 72B | route+thumb448 | docvqa | 99 | 87 | 0.925 | 85 | 0 | 96 | 1.8 |
| 72B | route+thumb448 | chartqa | 100 | 71 | 0.740 | 68 | 0 | 96 | 1.9 |
| 72B | route+thumb448 | all | 199 | 158 | 0.832 | 153 | 0 | 192 | 1.9 |

("No crop or page call" counts route answers whose route had no zoom or full-page step. The thumbnail arm always sends a 448 px thumbnail with the
OCR text, so "no crop or page call" there is **not** "no image".) Medians are the summed call latency per question. GPU-seconds were not recorded by the backend.

## Against the predictions in 169

| prediction | result |
|---|---|
| 7B: thumbnail beats plain route by ≥ 10/200 | **held** (substring 149 vs 105; relaxed 140 vs 108) |
| 7B: page beats plain route by ≥ 15/200 | **held** (166 vs 105; relaxed 166 vs 108) |
| 72B: thumbnail within 5/200 of page (relaxed) | **failed** (153 vs 165, −12) |
| 72B: plain route loses to page on ChartQA by ≥ 5/100 | **held** (relaxed 44 vs 76) |
| DocVQA: both route arms within 5/100 of page, both models | **partly**: thumbnail arms held (7B 85 vs 86, 72B 85 vs 89 relaxed); plain route failed (7B 74 vs 86, 72B 80 vs 89) |

## Reading

- **On real documents, with open models, the whole page is best.** The plain text-first route is far behind (7B 108 vs 166, 72B 124 vs 165 relaxed). The 7B
  asked for pixels on **1 of 199** questions, answering charts from OCR text. That's the same failure as on homework_v3 (165).
- **The thumbnail recovers most of the gap** (7B +32, 72B +29 relaxed) and is close to the page on DocVQA, but it still loses on charts (7B 55 vs 80, 72B 68 vs 76).
- The route is **not faster** here (median 1.0–1.9 s vs 0.7–2.1 s per question): it adds an OCR-text call before any image call.
- **Consequence for the app:** keep the whole page as the default for `local:` models in General mode (as 9278985 already does). The text-first saving is for
  models that decide well when to look (Haiku, per claude-andrew-b's billed run). Compare with that run by `question_id` once it's committed.
- Scope: 199 questions (99 DocVQA val, 100 ChartQA test), one run per arm, open models only.

## Context: Haiku on the same 199 items (claude-andrew-b's receipts `realdocs_haiku*`, re-scored here, not my run)

| Haiku arm | substring | relaxed | API $ (199 q) |
|---|---:|---:|---:|
| route (`realdocs_haiku`) | 161 | 120 | 0.0686 |
| whole page | 167 | 136 | 0.0618 |
| route + thumbnail (`realdocs_haiku_thumb`) | 160 | 119 | 0.0591 |

On real documents the route doesn't save money with Haiku either: charts are small images, so the page is cheap and the extra text call costs more.
**Do not read "Qwen beats Haiku" from these tables:** Qwen2.5-VL reports DocVQA and ChartQA as its own benchmarks and was very likely trained on their train
splits (in-distribution), and Haiku's longer answers are penalised by substring and relaxed scoring. The Haiku analysis is claude-andrew-b's.
