# Evidence Zoom: demo guide

**What it is.** A customer-service assistant that answers questions about whatever image a customer sends (a
receipt, a document, a form, a screenshot) while spending as few model tokens as possible. It answers and **shows
the evidence on the image** (the OCR box it read, or the region the model was sent), or **flags the question for
human review** when it cannot answer.
One automatic route, cheapest step first:

1. **OCR on the device ($0).** Local OCR reads the image first, with no model call.
2. **Configured form layouts: send only the region.** For a layout we configured (the demo's example is an
   accident-statement claim form), printed fields are answered from OCR directly. For questions that need pixels
   (which boxes are ticked, what the sketch shows), the form's own OCR'd layout picks the region, with no model
   call. The vision model sees only that crop, cut from the original high-resolution page. Regions far apart
   on the same rows (a tick and its row number) are stitched side by side.
3. **Common receipt fields with no model.** For change and item prices, or totals that pass a cash − change = total
   check, the number on the labelled row is read by local OCR and returned with 0 model tokens (development check:
   29 of 241 CORD receipt questions, 0 wrong).
4. **Any other image: a small page first.** The page is cropped to where OCR found text and asked at a small
   size (about 768 px). If the answer is found in the local OCR text, that is the reply. Otherwise the page is asked
   again at a higher resolution (≥ 1568 px if the photo allows; a small photo is never enlarged). This is where most customer images go. There is no region selection,
   so savings come from the image size only (see the general section below for what was measured).
5. **Personal data masked on the page path.** Before the page image is sent, lines that local OCR reads as card,
   IBAN, email, phone or AHV numbers are blacked out unless the question asks for that field (pattern-based, not a
   guarantee; configured-form crops are not masked). A redaction re-run on 241 CORD receipt questions triggered masking on none and flipped no answer between correct and incorrect (9 answer strings differed run to run); it does not test a case where masking activates.
6. **Repeated questions are free.** The same image, question and model returns the stored answer (0 tokens).
7. **Checkable answer or handoff.** The answer comes with a box on the original image (the OCR line it read, or
   the region sent to the model; not a citation by the model), so a person can check it. If the model reports the
   answer is not in the image, the demo displays “Human review needed.” and can prepare a copyable ticket for a person (question, what was tried,
   tokens spent, nearest OCR lines).

By default the demo runs **without any API key**. OCR is real. The vision model's replies are **replayed** from the
answers stored with each test form, and every replayed answer is labelled as such. A labelled **live mode** also
exists (`DEMO_LIVE=1` with an OpenRouter key; see `app/README.md`), checked end to end on Andrew's Mac.

---

## Tokens per correctly answered question (approved, `andrew-review-214-216`)

The numerator counts every question's input, cache and output tokens; correct handoffs are not in the denominator. Always name the baseline.

| set | our route | baseline |
|---|---:|---:|
| configured accident form (synthetic, Sonnet on both sides) | **774** | 5,696 (cached whole page); both 84 correct + 12 correct deferrals |
| second configured layout (synthetic, Haiku) | **841** (84 correct) | 5,946 (original page, 81 correct) |
| five unconfigured layouts (synthetic, Haiku) | 3,110 | 4,894 (original page); 2,986 (plain downscaled page) |
| real receipts, CORD (Haiku, OCR-checked ladder) | **1,380** | 2,727 (original photo); 179 correct + 60 correct deferrals + 2 wrong in both |

These runs predate the OCR field exits and redaction defaults now in the app.

**The app as shipped, held out (approved, `andrew-review-final-cord`).** On 248 questions about 60 fresh CORD validation receipts (a split nothing was tuned on), the router with the app's defaults answered 188 correctly and flagged all 60 unanswerable questions for review, with no wrong answers. Sending the original photo to the same model (Haiku): 187 correct, the same 60 flagged, 1 wrong. The router used **968 vs 2,740** provider tokens per correctly answered question (65% fewer) and cost $0.0234 vs $0.0584 (60% less); 31 questions were answered locally without calling Haiku. Scope: one paired run on receipts, provider prompt caching off, no masking triggered. With open models (Qwen 7B/72B, an earlier configuration) routing recorded more wrong answers (7B 31 vs 14; 72B 13 vs 6, across all 248), mostly from missed review flags.

## Run it (macOS, about 2 minutes the first time)

```bash
git clone git@github.com:Andrew1207-Yang/LauzHack.git evidence-zoom
cd evidence-zoom
./scripts/demo.sh
```

Open **http://localhost:8000**. The first run creates a `.venv` and installs the dependencies (FastAPI,
Pillow and a few others). OCR uses Apple Vision through a small Swift helper, which is compiled automatically on
first use (needs the Xcode command-line tools: `xcode-select --install`).

Use another port with `./scripts/demo.sh 8010`.

## Test it (no browser needed)

```bash
./scripts/test.sh
```

It runs six offline checks and ends with `ALL CHECKS PASSED`:

| check | what it proves |
|---|---|
| OCR field lookup | reading a field next to its label; refusing partial or uncertain IDs |
| router unit checks | OCR → visual hand-off, error handling (stubbed stages) |
| visual path geometry | on 96 test questions, grid → selected cells → crop → box mapped back to the page lands exactly on the true evidence (IoU 1.0) |
| eval harness unit checks | ~40 checks on scoring, pricing and guards |
| eval harness end to end | a mock run over the demo questions |
| demo smoke test | the exact judge script below, through the app's HTTP API |

---

## Three ways to run it

| command | visual answers from | needs | cost |
|---|---|---|---|
| `./scripts/demo.sh` | stored answers, **replayed** and labelled REPLAY | nothing | $0 |
| `./scripts/demo-live.sh` | **Claude Haiku 5.5** via OpenRouter, labelled MODEL | `OPENROUTER_API_KEY` (env or git-ignored `.env`) | ≈ $0.0002 per visual question, new calls stop once `APP_LIVE_MAX_USD` (default $1) is reached (a stop threshold, not a billing maximum) |
| `./scripts/demo-local.sh` | **Qwen2.5-VL-7B on this Mac** via Ollama, labelled MODEL | `brew install ollama`, `OLLAMA_CONTEXT_LENGTH=8192 ollama serve` (whole-page Compare needs more than the default 4096 tokens), `ollama pull qwen2.5vl:7b` (6 GB) | $0, and the document never leaves the machine |

All three use local OCR for printed fields and fall back to the labelled replay if a model call fails.
**On-device measurement** (Andrew's M3 Pro, 18 GB; layout 1, 96 questions; `eval/results/ondevice_qwen7b/`):
83/96 correct: printed fields 48/48 (OCR), not-on-form 12/12 (abstained), B's ticks 10/12, "did A tick 8" 8/12,
sketch 5/12. Each model call takes ~9 s (median) and up to ~23 s, so the app shows a waiting line while it works.
Present the tick questions on-device; the sketch question is answered better by Haiku (live mode).

**Switching models live:** when Ollama is running, `./scripts/demo-live.sh` also offers the on-device model in a picker
(top right); each answer names the model that produced it ("answered by … · cloud API / on this laptop"), and
**Compare: send the original, unmasked image** (under "How this was answered" on a live answer) sends the same question
with the whole page to the same model and shows both costs, token counts and times side by side (real calls; counts
toward the spend threshold).
**Avoid empty tick lists live:** on forms where driver B ticked nothing (eas-004, eas3b-002), Haiku tends to decline
and the on-device Qwen once listed all 17 boxes. Use pairs where B ticked something (eas-002, eas3b-003: the tour's pairs).

## Presenting: the guided tour

Click **▶ Guided tour** (top bar). Each **Next ▶** performs one step of the judge script below (pick the form, ask,
switch to form b, then layout 3) and shows one sentence to say. Each answer shows its path (Read locally → crop or
small page → OCR check → answer or review) and its tokens against the original image; **How this was answered**
under it unfolds the plain-language explanation, the route and the cost. **How it works** (top bar) opens a diagram
of the four steps that lights up step by step and can start the guided tour. **What we measured** (top bar) opens
the approved results, each with its baseline, limits and the path of its receipt in the repository; the held-out
receipts result comes first.

## The two-minute judge script (live: `./scripts/demo-live.sh`)

The story: a customer sends a photo and asks a question, the way they would ask a support agent.

1. **Upload a phone photo of a receipt** (drag it onto the page) and click **"What is the total amount?"**
   - The answer comes back with "✓ found in the page text": green boxes mark the line(s) where that total is printed.
   - The pill shows its input tokens against sending the original photo.
   - "What the model saw" shows the small cropped page; the image outside the region sent is dimmed.
2. **Ask "How much VAT was paid in total?"** The image is read from the provider's prompt cache. If the receipt shows a card number or phone number, the card says it was masked before sending.
3. **Ask something the receipt cannot answer** ("What is the customer's loyalty number?").
   - The app reports "Human review needed" instead of inventing an answer. If the model says on the small page that the information is not there, it stops early; otherwise it may first try a sharper image (in the live check of message 243 it did, twice).
   - **Create ticket for a human agent** prepares a copyable ticket: the question, what was tried, the tokens spent and the nearest page text.
4. **Switch the model** (top right) to the on-device Qwen and ask again: the same route at $0; with the default local endpoint the image never leaves the laptop.
5. **Pick a sample claim form** ("Accident claim form #2") and ask the policy number, then which boxes driver B ticked.
   - The policy number is read by OCR: 0 model tokens.
   - The ticks are answered from a ~150-pixel-wide crop of B's tick column, picked by the form's own layout.
   - Switch to **version B** (one tick moved): the answer and the box move.
6. **The savings card** (top right) sums the session: input tokens sent against sending the original images, and the projection to 1,000 questions.

## What is new here

- **OCR as a free check.** A small image is asked first. Its answer is accepted only if that string is in the page's own OCR text (a check that it is printed, not that it is right); otherwise a sharper image is sent. Coarse-to-fine resolution with a model-free stopping rule, through a hosted API.
- **Layout-anchored crops without a model.** On a configured form, OCR finds the printed anchors (row numbers, labels) and the crop is cut from them: no model chooses where to look.
- **Zero-token exits.** Printed fields, and common receipt fields with a consistency check, are answered by OCR alone.
- **Honest accounting.** Each result names its baseline. Large-image cost is capped at what the provider was measured to bill. The negative results (text-first on real documents, pointing with Qwen boxes, re-typesetting, speculative local-then-cloud) are kept in the repo.

## The key-free walkthrough (replay, no API key: `./scripts/demo.sh`)

1. In the **Pick a sample…** menu, choose **Accident claim form #2 (two versions: B's ticks differ)**.
   Version A opens. Version B is the same form with one of driver B's ticks moved.
2. Click the suggestion **"What is vehicle A's insurance policy number?"**
   You see the **LIVE OCR** badge, the policy number, a green box on it in the page, and the route
   `ocr → answer` at **$0**.
3. Click **"Which circumstance boxes did driver B tick?"**
   You see the **REPLAY** badge and the answer **8**. The route is `zoom anchor:ticks → answer`.
   Under the answer is the one image that would be sent to a model: the **anchor crop** (about 147×883 px),
   with the row numbers stitched next to driver B's tick column. On the page, a pink box marks the tick.
4. Click **version B** and ask the tick question again. The answer changes to **7** and the box moves one row up.
   The line above the page now shows `a: 8 · b: 7`; switching back to form a keeps its conversation.
   The policy number is still read by OCR, because only the tick differs.
5. Optional: click **"What is driver A's driving licence number?"** (not on the form). No anchor applies, so the
   route falls back to the page (cropped to its text area and downscaled) and the replayed answer is "not on the
   form": the bot says it cannot answer and flags the question for human review. Type **"Is there a dog in the picture?"** and you get **NO ANSWER**
   with the reason: there is no stored answer to replay, so nothing is invented.

The **savings card** compares this route with sending the original images; the **Cost detail** under it compares
with the full page with and without prompt caching. **All costs are estimates** from token arithmetic.

6. **A different layout.** In the menu, choose **Accident claim form, style 3 #3**. This form has a
   different design: stacked vehicle bands, values under their labels, bare row numbers, both tick columns left of
   the text. The built-in rules cannot read it; a short **configured template** (10 lines) can. Ask the policy
   number: **LIVE OCR**, route `ocr → answer`, and the answer says it came *from the line labelled "Policy No"*.
   Ask B's ticks: the template picks B's tick column (`zoom anchor:ticks`); form a has 3, 16 and form b has 2, 3.
   Optional: on **Accident claim form, style 2 #1** the policy number is *not* answered by OCR. Vision reads `J1-…` for
   `JI-…`, and the look-alike guard sends it to the page instead of risking a wrong ID.

## Beyond claim forms: the general assistant (live only)

**One automatic route for every image (no picker).** OCR runs locally first. If it recognises a configured claim-form layout, the router answers printed fields from OCR ($0) or sends the model only the located region. For anything else (receipts, uploads, worksheets), it sends the page as one image, cropped to where OCR found text and downscaled: short side ≥ 768 px, long side ≥ 1024 px, cap 2400 px. On 70 DocVQA scans, the whole page at 1024 px had the same mean score as full size, at about a third of the cost (`REPORT_realdocs.md`, resolution frontier). Infographics lost accuracy when downscaled. The OCR-area crop and this size rule were set from that test and are measured only as part of the whole route (the held-out receipts result above).
Example: a 4284×5712 phone photo of a receipt is sent as a cropped, downscaled page. Qwen2.5-VL-7B on the laptop read the total and the VAT correctly (one receipt, development check). Sending the original photo to Haiku was billed 4,773 input tokens: the provider downscales large images itself, so the original-image baseline is capped at that measured maximum.

**The OCR-checked ladder** (default on; approved in `andrew-review-ladder`). The model first sees a smaller page (about 768 px). The answer is accepted only if it appears in the page's local OCR text; otherwise the page is sent again at ≥ 1568 px (or at the photo's own size if smaller).
- **DocVQA scans** (100 questions, Haiku):
  - 96 correct, the same as the original full page (a separately prompted baseline);
  - ANLS 0.920 vs 0.931;
  - about 1,574 vs 4,587 provider tokens per correct answer, 44% of the charge.
- **Real receipts** (CORD, 241 questions), against the fixed-size page: the same 179 answered correctly and 60 correctly flagged for human review. The answers matched the reference wording more closely (ANLS 0.970 vs 0.924), for 1,380 vs 1,218 tokens per correct answer.
- **Limits:** always name the baseline. The 768/1568 pairing was chosen on a different DocVQA sample. One run each.

Uploads have no replay, so they need `./scripts/demo-live.sh` or `./scripts/demo-local.sh` (Ollama: `OLLAMA_CONTEXT_LENGTH=8192 ollama serve`).

Why the app does not use text-first any more: small open models answered visual questions from OCR text instead of asking for the image (Qwen 7B 53/96 vs 75/96 with the page, `REPORT_homework_v3_qwen7b.md`). On real documents text-first scored lower overall (`REPORT_realdocs.md`). The cropped, downscaled page is meant to avoid both.

## Measured, billed (OpenRouter receipts; synthetic forms)

- Accident statement, 96 questions: Haiku 5.5 on our route **96/96 for $0.0098**; Sonnet 5.5 on the cached whole
  page **96/96 for $0.2425** (24.7× lower API charge). Same model (Sonnet on both sides): $0.162 vs $0.243; the
  saving is the 48 questions OCR answers locally.
- Second configured layout, 12 new forms generated after the template was frozen: route **96/96 for $0.010**,
  original page 93/96 for $0.052 (Haiku on both sides).
- Five unconfigured layouts, 416 questions: all went to a full-page call; Haiku 401 through the router, 397 from
  the original page. The cost difference there comes from the page resolution, not routing.
- Total API spend: through the resolution tests we can account for about $2.26 of the $10 credit: the $1.4979 key reading (message 131) plus committed worksheet ($0.2955), handwriting ($0.0512) and real-document ($0.4142) run charges. The provider dashboard gives the live balance.

Sources and limits: `docs/NARRATIVE.md` §3. The app's session meter is a per-question **estimate**; the figures
above are receipts.

## What is real, what is replayed, what is estimated

| | status |
|---|---|
| OCR answers and their boxes | **real**: Apple Vision on your machine |
| routing decision, anchor selection, crop (or full page), box mapping | **real** code path |
| the vision model's reply (the answer and its box) | **replayed** from the test form's stored answer (`pipeline/visual/replay.py`) |
| token counts and $ | **estimated**, calibrated on billed Claude usage (~width × height / 800 tokens per image up to the provider cap; a Haiku/OpenRouter probe billed a 24.5 MP photo at 4,773 input tokens, so the estimate is capped at 4,750 image tokens; list prices in `eval/pricing.py`) |

Measured results, their limits and their provenance are in `docs/NARRATIVE.md` (the reviewed source for any
number you quote). In short: on the configured templates (the accident statement and a second layout), OCR
answers the printed fields locally and the anchored crop lets a small model answer the visual questions; on
layouts and document types we did not configure, the anchors find nothing and the page fallback applies.

---

## Where things are

| path | what |
|---|---|
| `app/` | web app (FastAPI + one HTML page): `server.py`, `static/` |
| `pipeline/router.py` | router v3: OCR answer → anchored crop (`pipeline/anchor/`) → full-page fallback |
| `pipeline/templates/` | declarative per-layout templates (short config + one generic engine) used when the built-in rules cannot read a layout |
| `pipeline/ocr/` | OCR route (Apple Vision helper + field lookup) |
| `pipeline/visual/` | crop stitching (`View`), `zoom_answer`, overview path (not the default); `replay.py` = key-free stand-in for the model |
| `eval/` | evaluation harness, test forms (`eval/data/accident_statement/`), scorecard |
| `scripts/demo.sh`, `scripts/test.sh` | run the demo, run all checks |
| `README.md` | overview, results and links to the evidence |
| `agent-messages/` | the team's coordination log (background, not needed to run the demo) |

## Troubleshooting

- **Every answer is REPLAY or NO ANSWER, never LIVE OCR.** The OCR helper could not be built. Run
  `xcode-select --install`, then restart `./scripts/demo.sh`. OCR is macOS-only for now.
- **Port already in use.** Use `./scripts/demo.sh 8010`.
- **Uploading your own image.** It works, but visual questions get NO ANSWER, because there is no stored
  answer to replay without a live model. Text questions about a similar two-column form still go through OCR.
- **Start over.** Delete `.venv/` and rerun the script.
