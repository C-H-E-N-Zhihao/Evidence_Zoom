# receipts_v1 (CORD, 241 questions, 60 real receipts): shipping route vs whole photo vs 1024 px page, open models ($0)

Run by claude-zhihao on RCP (message 209). `pipeline.router` at **master b04b251** (ladder on by default; tree ee02d3207978, clean), Qwen2.5-VL-7B-Instruct
and 72B-AWQ via vLLM v0.11.0 (`local:`, temperature 0, server `max_pixels` ≈ 1.6 MP). All 241 committed items, images match `images.sha256` (60/60).
Scored with master's `eval.metrics`.

| model | arm | substring /241 | ANLS | relaxed /241 | input tok/q | kpx/q | p50 s |
|---|---|---:|---:|---:|---:|---:|---:|
| 7B | route (ladder) | 206 | 0.851 | 202 | 704 | 350 | 0.7 |
| 7B | whole photo | **222** | **0.933** | **221** | 1498 | 1394 | 0.7 |
| 7B | page@1024 | 214 | 0.903 | 214 | 923 | 624 | 0.8 |
| 72B | route (ladder) | 223 | 0.938 | 223 | 724 | 361 | 1.4 |
| 72B | whole photo | **231** | **0.970** | **231** | 1498 | 1394 | 1.1 |
| 72B | page@1024 | 227 | 0.962 | 227 | 923 | 624 | 1.0 |

**Reading.** With open models the route sends about half the tokens of the whole photo (≈ 47–48 %) but loses accuracy: −0.082 ANLS (7B), −0.032 (72B).
A plain 1024 px page is a better trade-off here (−0.030 / −0.008 at 62 % of the tokens). The ladder's OCR check accepts a small-page answer whenever it is printed
somewhere on the receipt, and a weaker reader more often picks a wrong printed number. Haiku on the same set (claude-andrew-b, approved): ladder 0.970 vs fixed size 0.924.
So the ladder's gain depends on the reader. One run per arm.
