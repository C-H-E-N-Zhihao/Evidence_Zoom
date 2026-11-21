# Evidence Zoom: demo narrative and claims ledger

Owner: claude-guanyu (narrative), reconciling the rehearsal and the scorecard (handoff in message 044 from claude-andrew-b). Every number below carries a status and a source. **MEASURED** = observed in a run in the repo. **ORACLE** = geometry check with gold answers. **ESTIMATED** = token and price arithmetic. **PENDING** = not run yet. When a number changes, change it here and in its source together.

## 1. The story in four sentences

1. A claims handler at AXA asks questions about an accident statement: a policy number, which boxes a driver ticked, who hit whom in the sketch.
2. Sending the whole page to a vision model for every question is the expensive default.
3. For a known form template, Evidence Zoom answers printed fields with local OCR for $0, and sends a model only the pixels a question needs, chosen from the template's layout. On the template it was built for (36 visual questions, one layout), a 7B open model reading those pixels scored 22/36 against 20/36 for a 72B model reading the full page, and the 72B model scored 36/36 on the crops. **On an unseen layout, router v1 was much worse than simply sending the page:** the local stages declined everything, its overview-zoom fallback could not find the evidence, and the models invented missing fields. Router v2 (`freeze-router-v2`) therefore sends the whole page when the local stages decline. That is a design choice, still untested on unseen data. The rules are per-template configuration, which suits a standardised form such as the European Accident Statement. They are not general document understanding.
4. OCR answers and anchor-crop answers point to the region of the original page they came from, so the handler can check them. Answers from a model reading the whole page often come without a usable box, so evidence hit was ~0 % for the full-page baselines in the local runs.

## 2. What the judge sees (two-minute script)

Launch: `./scripts/demo.sh` (macOS for live OCR) → `http://localhost:8000`. Full steps and controls: message 027 and the app README.

| Step | What happens | Status |
|---|---|---|
| Ask the policy number on form `eas-002 a` | LIVE OCR badge, answer, green box on the value, route `ocr → answer`, $0 | MEASURED on one Mac, claude-andrew-b's (messages 031, 045) |
| Ask which boxes driver B ticked | REPLAY badge, answer 8, the overview and the row-aligned crop actually sent, box on row 8 | Geometry real; the model's two replies are replayed from gold labels (banner says so) |
| Switch to form `b` (one tick moved) and ask again | Answer 7, box moves to row 7; the policy answer is unchanged | Same as above |
| Ask an off-script question ("Is there a dog?") | NO ANSWER with the reason; nothing invented | MEASURED (031, 045) |
| Cost meter | Route cost against the full page, cached and uncached | ESTIMATED; failures now charge the overview call (fix after 031) |

**Say out loud:** "The OCR answers are live. The visual answers in this mode are replays of the right answer, to show the mechanics. Live model results are in section 3."

## 3. Claims ledger

### Safe to claim

All rows in this list are on the **development layout**, the 12 forms the rules were written on, unless marked held-out. Say that.

| Claim | Status | Source |
|---|---|---|
| **Held-out layout:** run unchanged on a second layout, the frozen OCR route answers 0/48 and the anchor selects 0/36. Everything falls back to the model, with 0 wrong OCR answers. The $0 savings do **not** transfer to an unseen layout without configuring it. | MEASURED (held-out v2; re-run 7d48ab4 prints `pipeline/` tree a989fe9 = frozen tag `freeze-anchor-ocr-v1`; coverage bench likewise) | `eval/results/REPORT_heldout_v2_ocr.md`, `REPORT_heldout_v2_anchor_coverage.md` (2189570), message 059 |
| **End to end, held-out layout v2, all 96 questions:** the route (OCR → anchor → overview-zoom fallback) gets 7B **35/96** against 72/96 on the full page, and 72B **50/96** against 91/96. On the missing-field question the route invents a value in 7B 12/12 and 72B 5/12 cases, the full page in 5/12 and 0/12 | MEASURED (frozen tag 0b2a138, `meta.commit`; pipeline tree stated in the README, since that harness predates the automatic field). Counts re-derived from the JSON with jq | `eval/results/model_scale/e2e_frozen/` (794ef03) |
| **End to end, development layout, all 96 questions:** OCR → anchor crop → overview gets 7B 79/96 against 75/96 on the full page, and 72B 95/96 against 80/96 | MEASURED. 1 of the route's misses per model is a setup error (OCR helper missing on the first item, eas-001a-q1), fixed in the harness at 458b8cb | `eval/results/model_scale/e2e/README.md` (d944d8f) |
| OCR answers 48 of 96 synthetic questions (all text and layout questions), all correct, **0 wrong answers** | MEASURED (development layout) | `eval/results/SCORECARD.md` §1 |
| 0 wrong OCR answers under all 10 tested degradations (JPEG, blur, 2° and 5° tilt, perspective, phone photo, downscaling): 48 correct of 60 OCR-eligible questions on each, except 24 at 768 px (the rest fall back) | MEASURED (development layout). **Not a general safety guarantee:** on v2, Vision read `JI-9779-2542` as `J1-9779-2542`. Only an unrelated header check stopped that becoming a wrong answer (059). | `eval/results/REPORT_ocr_robustness_82f3112.md` |
| OCR takes ~0.6 s for the first question on a page and ~10 ms for later ones (page index reused) | MEASURED | andrew-ocr, 88119ad |
| Questions about a field that is not on the form: 72B declines 12/12 on the route; **7B invents an answer in 2/12** ("D. Dubois", "H. Keller" for a licence number), although the 7B full page declines 12/12. In the key-free demo the "no answer" comes from replay | MEASURED (development layout, e2e) | `eval/results/model_scale/e2e/run_20261121-160458.json`, message 045 |
| A small open model reads better from the right crop than from the page: Qwen2.5-VL-7B 42 % on the full page → **67 % on the correct crop**, at ~1/4 of the input tokens | MEASURED (36 visual questions, local GPU) | `eval/results/REPORT_local_qwen7b_visual.md` |
| The layout tells us where to look without any model: the OCR-chosen crop contains the evidence for **36/36** visual questions on clean forms, and still 36/36 under JPEG, blur, 1024/768 px and 2°/5° tilt (deskew) | MEASURED (selection only, $0) | `eval/results/REPORT_anchor_coverage.md` at 27dca74 |
| The OCR-chosen crop is small in pixels: median 147×883 (ticks), 482×161 (one tick row), 1568×468 (sketch), against 1700×2200 for the page. Token figures for these crops are withheld until recalibration (billed page ≈ 4,900 tokens, message 066) | MEASURED (pixel sizes); tokens withheld | `eval/results/REPORT_anchor_coverage.md` at 27dca74 |
| Ticks can be read with no model at all on upright pages at ≥ 768 px: 24/24 | MEASURED (classical control) | message `andrew-checkbox-control` |
| **With the OCR-chosen crop, the large open model answers every visual question:** Qwen2.5-VL-72B 36/36 (100 %) against 20/36 (56 %) on the full page, with ~1/3 of the input tokens (660 vs 2,120 per question) | MEASURED (36 visual questions, one synthetic layout, local GPU) | `eval/results/model_scale/REPORT.md` (b8f1c34) |
| **7B on the OCR-chosen crop vs 72B on the full page:** Qwen-7B 22/36 on the anchor crop, Qwen-72B 20/36 on the full page | MEASURED, descriptive only: one layout, 36 items, no equivalence margin tested. Quote both counts, not "matches" or "beats" | `eval/results/model_scale/REPORT.md` (b8f1c34) |
| Vision models cannot choose the region themselves, at either size: forced to pick cells, 7B covers the evidence in 0/24 zooms and 72B in 3/36; a 72B selector feeding a 7B reader also covers 3/36. Allowed to answer from the overview, both answer directly and never zoom | MEASURED | same; selection measured with `eval.metrics.zoom_coverage` |

### Claim only with the stated condition

> **Recalibration pending:** billed usage shows a full 1700×2200 page costs **~4,900 input tokens** on Claude 5.5 via OpenRouter (smoke test, message 066), against the ~1,531 that all ESTIMATED rows below and `SCORECARD.md` assume (w·h/750 after downscaling). Every ESTIMATED $ and token ratio here is therefore **superseded** until the paid sweep's billed per-input numbers are folded in. Do not quote them.

| Claim | Condition to say aloud | Status | Source |
|---|---|---|---|
| For one question, OCR-first with zoom costs about **1/3 of sending the page** on the same model | estimated tokens and list prices; thinking tokens excluded; synthetic forms | ESTIMATED | `SCORECARD.md` §4 |
| OCR-first with zoom is never more than ~10 % above the best fixed strategy over 1–8 questions per form, and up to 3.3× cheaper than caching the page | same as above; switching strategy mid-session is never cheaper | ESTIMATED | `SCORECARD.md` §4b, message 032 |
| The visual route sends ~725 image tokens per visual question against ~1,531 for the page | oracle selection; the OCR-chosen crop is smaller for ticks (~103–173) and similar for the sketch (~978) | ORACLE / ESTIMATED | `SCORECARD.md` §2, `REPORT_anchor_coverage.md` |
| 7B on the anchor crop needs ~1/27 of the compute of 72B on the full page (11.7 vs 316 TFLOPs per question) | compute = 2 × parameters × tokens, a hardware-neutral proxy; measured GPU seconds are 0.66 vs 1.91 per question but on different GPU types (A100 vs H100) | ESTIMATED (FLOPs) / MEASURED (latency) | `eval/results/model_scale/REPORT.md` |

### Do not claim (yet)

| Not supported | Why | What would support it |
|---|---|---|
| "Zoom is cheaper than the page" in general | With a cached page and many questions per form, the page is cheaper (k ≥ 7, ESTIMATED) | Measured billed usage over realistic question counts |
| "The model finds the right region itself" | **Measured false** at 7B and 72B (see "safe to claim"); the region must come from the layout | – (settled) |
| The OCR and anchor rules generalize to other forms | **Measured false** on the held-out layout v2 (0/48 OCR answers, 0/36 anchors; all fall back safely). Causes: v2 repeats the vehicle header, and its sketch precedes the circumstances (059) | Per-template configuration, or a layout-independent selector, then re-test on unseen layouts and other document types (claude-andrew-b, 059) |
| "OCR exits are safe in general" | On v2 an I→1 misread (`J1-9779-2542`) was stopped only by an unrelated check | Normalise look-alike characters for IDs (I/1, O/0) and re-test held-out |
| Any billed $ saving | No paid run exists; all $ are estimates | `eval/first_paid_sweep.sh` (message 050) |
| Works on real claims | All forms are synthetic renders. Tilt up to 5° is handled by OCR and by the anchor crop (deskew). Perspective and phone-photo coverage are not cleanly measured (gold boxes not transformed), and 2/12 phone-photo tick questions find no anchor and fall back | Real photographed forms; gold boxes transformed for perspective |
| "Local is free" | GPU time is not free | Report GPU s/q and price it with `EVAL_GPU_USD_PER_HOUR` (stated rate) |

## 4. Design decisions the numbers justify

1. **OCR first, always**, but per template. On the development layout it handled half the questions at $0 with no wrong answers. On an unseen layout it declines every question and passes it on to the model route; the cost and accuracy of that are measured only end to end (pending for v2).
2. **Choose the crop from the layout, not from the model.** Neither the 7B nor the 72B model can pick regions; OCR anchors cover the evidence at $0, and with them 72B answers 36/36. This is the cheap stand-in for the original idea of a "question decides where detail is acquired" representation (FlexTok probe, message `andrew-flextok-probe`).
3. **No mid-session switch to a cached page.** Every switch point is dominated (§4b). If a long session on one form is expected up front, cache the page from question 1.
4. **Say "no answer" rather than guess**: a goal, not yet a measured property. Measured: the overview-zoom fallback makes models invent missing fields (v2: 7B 12/12, 72B 5/12), more than the full page does (5/12, 0/12).
5. **When the local stages decline, send the whole page, not the overview zoom** (claude-zhihao 062; router v2, frozen at `freeze-router-v2` = 1f28ca7). This is design, not a result. The page fallback is **not** the same request as the `full_image` baseline: it uses a resized view and a different prompt (codex-guanyu, page-fallback audit). Matching full-page accuracy, missing-field behaviour or cost is a **hypothesis**, to be tested on the blind document families (064).

## 5. Open results that would change this page

| Result | Owner | Changes |
|---|---|---|
| `experiments/model_scale` | claude-zhihao | **done** (b8f1c34), folded in above |
| End-to-end OCR → anchor → overview on all 96 | claude-zhihao (in progress) | the headline end-to-end accuracy and route mix |
| Crop-budget sweep on local Qwen (192/384/768 px, overview + crop) | request 039 to claude-zhihao | how small the crop can be |
| First paid sweep + `billing_probe`: one command, `eval/first_paid_sweep.sh` (5 capped steps) | waiting on Andrew's API key | every ESTIMATED $ row |

## 6. Provenance notes (judge)

- **Development set = evaluation set so far.** The OCR rules, anchor selector and `checkbox_pixels` were built on the same 12 synthetic forms of one layout that every number above comes from. The held-out layout test is the check (release checklist B). Code frozen at tag `freeze-anchor-ocr-v1` = 0b2a138 (message 056); provenance checked independently by codex-guanyu.
- **Post-hoc fix:** the anchor's q5 prompt note (0b2a138, message 055) was written after seeing 7B abstain on the 4 "no" forms. The model-scale numbers (b8f1c34) are from **before** that note. Any re-run on the same 12 forms after it is labelled "tuned on test errors" and does not replace them.

## 7. Awaiting release review (codex-guanyu), not yet in the claims lists

- **Blind document families** (944e679, message 071): 4 new types (breaker panel, repair invoice, travel claim, vehicle damage), 320 items, generated without reading `pipeline/`. At `freeze-router-v2` (`pipeline_equals_freeze True`): OCR 0/320 exits, 0 wrong; router v2 sends **all 320 to the full page**. This matches the prediction stated before opening them (064). The frugal path contributes nothing outside the configured template, and costs no extra error. Model accuracy on these sets is not measured.
