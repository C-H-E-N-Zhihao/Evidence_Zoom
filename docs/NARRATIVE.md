# Evidence Zoom: demo narrative and claims ledger

Owner: claude-guanyu (narrative), reconciling the rehearsal and the scorecard (handoff in message 044 from claude-andrew-b). Every number below carries a status and a source. **MEASURED** = observed in a run in the repo. **ORACLE** = geometry check with gold answers. **ESTIMATED** = token and price arithmetic. **PENDING** = not run yet. When a number changes, change it here and in its source together.

## 1. The story in four sentences

1. A claims handler at AXA asks questions about an accident statement: a policy number, which boxes a driver ticked, who hit whom in the sketch.
2. Sending the whole page to a vision model for every question is the expensive default.
3. Evidence Zoom answers printed fields with local OCR for $0, and sends a model only the pixels a question needs, chosen from the page layout.
4. Every answer points to the region of the original page it came from, so the handler can check it.

## 2. What the judge sees (two-minute script)

Launch: `./scripts/demo.sh` (macOS for live OCR) → `http://localhost:8000`. Full steps and controls: message 027 and the app README.

| Step | What happens | Status |
|---|---|---|
| Ask the policy number on form `eas-002 a` | LIVE OCR badge, answer, green box on the value, route `ocr → answer`, $0 | MEASURED on two machines (messages 031, 045) |
| Ask which boxes driver B ticked | REPLAY badge, answer 8, the overview and the row-aligned crop actually sent, box on row 8 | Geometry real; the model's two replies are replayed from gold labels (banner says so) |
| Switch to form `b` (one tick moved) and ask again | Answer 7, box moves to row 7; the policy answer is unchanged | Same as above |
| Ask an off-script question ("Is there a dog?") | NO ANSWER with the reason; nothing invented | MEASURED (031, 045) |
| Cost meter | Route cost against the full page, cached and uncached | ESTIMATED; failures now charge the overview call (fix after 031) |

**Say out loud:** "The OCR answers are live. The visual answers in this mode are replays of the right answer, to show the mechanics. Live model results are in section 3."

## 3. Claims ledger

### Safe to claim

| Claim | Status | Source |
|---|---|---|
| OCR answers 48 of 96 synthetic questions (all text and layout questions), all correct, **0 wrong answers** | MEASURED | `eval/results/SCORECARD.md` §1 |
| 0 wrong OCR answers under JPEG, blur, 2° tilt, perspective and phone-photo degradations | MEASURED | `eval/results/REPORT_ocr_robustness_35c7c16.md` |
| At a 5° tilt, header-aligned rows raise correct OCR answers from 4 to 48 of 60, with 0 wrong | MEASURED, **author-reported only**: README at ac9b30e; no report file committed yet (the linked report predates the fix) | re-run `python -m bench.ocr_robustness` at ≥ ac9b30e and commit it (asked in message 047) |
| OCR takes ~0.6 s for the first question on a page and ~10 ms for later ones (page index reused) | MEASURED | andrew-ocr, 88119ad |
| Questions the system cannot answer get no answer, not an invented one | MEASURED (replay mode) | message 045 |
| A small open model reads better from the right crop than from the page: Qwen2.5-VL-7B 42 % on the full page → **67 % on the correct crop**, at ~1/4 of the input tokens | MEASURED (36 visual questions, local GPU) | `eval/results/REPORT_local_qwen7b_visual.md` |
| The layout tells us where to look without any model: the OCR-chosen crop contains the evidence for **36/36** visual questions on clean forms | MEASURED (selection only, $0) | `eval/results/REPORT_anchor_coverage.md` |
| Ticks can be read with no model at all on upright pages at ≥ 768 px: 24/24 | MEASURED (classical control) | message `andrew-checkbox-control` |

### Claim only with the stated condition

| Claim | Condition to say aloud | Status | Source |
|---|---|---|---|
| For one question, OCR-first with zoom costs about **1/3 of sending the page** on the same model | estimated tokens and list prices; thinking tokens excluded; synthetic forms | ESTIMATED | `SCORECARD.md` §4 |
| OCR-first with zoom is never more than ~10 % above the best fixed strategy over 1–8 questions per form, and up to 3.3× cheaper than caching the page | same as above; switching strategy mid-session is never cheaper | ESTIMATED | `SCORECARD.md` §4b, message 032 |
| The visual route sends ~725 image tokens per visual question against ~1,531 for the page | oracle selection; the OCR-chosen crop is smaller for ticks (~103–173) and similar for the sketch (~978) | ORACLE / ESTIMATED | `SCORECARD.md` §2, `REPORT_anchor_coverage.md` |

### Do not claim (yet)

| Not supported | Why | What would support it |
|---|---|---|
| "Zoom is cheaper than the page" in general | With a cached page and many questions per form, the page is cheaper (k ≥ 7, ESTIMATED) | Measured billed usage over realistic question counts |
| "The model finds the right region itself" | Qwen-7B never asks to zoom; forced, it picks the wrong cells (25–28 %) | 72B or OCR-anchored selection run (PENDING: `experiments/model_scale`) |
| "The OCR-chosen crop fixes accuracy" | Coverage is measured; accuracy with a model reading that crop is not | `pipeline.anchor:factory` on local Qwen (PENDING, message 043) |
| Any billed $ saving | No paid run exists; all $ are estimates | First paid sweep after `billing_probe` (message 017) |
| Works on real claims | All forms are synthetic renders; tilt ≥ 5° breaks the tick-column crop | Real photographed forms |
| "Local is free" | GPU time is not free | Report GPU s/q and price it with `EVAL_GPU_USD_PER_HOUR` (stated rate) |

## 4. Design decisions the numbers justify

1. **OCR first, always.** It handled half the questions at $0 with no wrong answers, including on degraded inputs.
2. **Choose the crop from the layout, not from the model.** The 7B model cannot pick regions, and OCR anchors cover the evidence at $0. This is the cheap stand-in for the original idea of a "question decides where detail is acquired" representation (FlexTok probe, message `andrew-flextok-probe`).
3. **No mid-session switch to a cached page.** Every switch point is dominated (§4b). If a long session on one form is expected up front, cache the page from question 1.
4. **Say "no answer" rather than guess.** The router falls back, the visual route abstains, and the meter charges the attempt.

## 5. Open results that would change this page

| Result | Owner | Changes |
|---|---|---|
| `experiments/model_scale` (7B vs 72B × full page / gold crop / anchor crop / model zoom / split) | claude-zhihao | the "do not claim" rows on region selection and anchor accuracy |
| Crop-budget sweep on local Qwen (192/384/768 px, overview + crop) | request 039 to claude-zhihao | how small the crop can be |
| First paid sweep + `billing_probe` | waiting on Andrew's API key | every ESTIMATED $ row |
