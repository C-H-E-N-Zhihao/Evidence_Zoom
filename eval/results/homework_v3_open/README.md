# General route with open-weights models on the blind worksheet set (homework_v3), $0 provider charge

Run by claude-zhihao on RCP (message 164, warm-up before the real-document sample). `pipeline.general` from a worktree at **`freeze-general-v2`**
(`pipeline_tree` e128edd722cc, `pipeline_equals_freeze: true`, clean). Models served by vLLM v0.11.0 on RCP via the `local:` backend:
Qwen2.5-VL-72B-Instruct-AWQ (H100) and Qwen2.5-VL-7B-Instruct (A100). Temperature 0. Scorer: `eval.metrics.answer_correct` (same as 155).

**Image caveat:** homework_v3 images are git-ignored; I regenerated them with the committed generator (seed 50505) under **Pillow 13.0.0**.
`items.jsonl` is byte-identical to the committed one, but the PNG bytes differ from `images.sha256` (digest b6ce64a53a1fc6b1). Same content, different
rasterisation. So this is not the exact image set of the Haiku run in 155.

| model | arm | correct /96 | text /36 | mixed /18 | visual /30 | unanswerable /12 | text questions without an image |
|---|---|---:|---:|---:|---:|---:|---:|
| Qwen 72B-AWQ | route | 79 | 34 | 11 | 24 | 10 | 34/48 |
| Qwen 72B-AWQ | whole page | **88** | 36 | 13 | 27 | 12 | – |
| Qwen 7B | route | 48 | 35 | 8 | **5** | **0** | 36/48 |
| Qwen 7B | whole page | **74** | 36 | 7 | 23 | 8 | – |
| *(155, Haiku, committed images)* | *route / page* | *96 / 95* | | | | | *44/48* |

Median latency per question (all calls): 72B route 1.2 s vs page 0.9 s; 7B route 0.6 s vs page 0.7 s. GPU-seconds were not recorded by the backend for these runs.

**Reading.** The general route lets the **model decide when to look at pixels**. Haiku makes that decision well (155); the open models do not.
7B answers visual questions from OCR text instead of asking for the image (visual 5/30) and never abstains on unanswerable ones (0/12). 72B is better
but still loses 9 questions to the page. This is the same weakness measured earlier for evidence selection (7B 0/24, 72B 3/36), and it explains why the
insurance route, whose selector uses no model (OCR anchor), works with open models while the general route does not. **Consequence:** for in-house
open models, send the whole page or keep a model-free selector; don't use the model-gated text-first route. One run, synthetic worksheets.
