# Evidence Zoom: demo guide

**What it is.** A claims handler asks questions about an accident-statement form. The app answers and
**points to the evidence on the page**, while spending as little model compute as possible:

1. **OCR first.** If the answer is printed text (a policy number, a registration), local OCR reads it.
   This costs $0 and needs no model call.
2. **Crop from the form's own layout.** If the answer needs pixels (which boxes are ticked, what the sketch
   shows), the OCR'd layout of this form template (row numbers, column headers, section headings) picks the
   region, with no model call. A vision model sees only that crop, cut from the original high-resolution
   page. Regions far apart on the same rows (a tick and its row number) are stitched side by side, so the
   crop stays small but keeps its meaning.
   **If the layout is not recognised** (another template, another document type), the model gets the
   **full page** instead: the frugal path only exists for configured templates.
3. **Grounded answer.** The answer comes back with a box on the original page, so a human can check it.

By default the demo runs **without any API key**. OCR is real. The vision model's replies are **replayed** from the
answers stored with each test form, and every replayed answer is labelled as such. A labelled **live mode** also
exists (`DEMO_LIVE=1` with an OpenRouter key; see `app/README.md`), checked end to end on Andrew's Mac.

---

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
| `./scripts/demo-local.sh` | **Qwen2.5-VL-7B on this Mac** via Ollama, labelled MODEL | `brew install ollama`, `ollama serve`, `ollama pull qwen2.5vl:7b` (6 GB) | $0, and the document never leaves the machine |

All three use local OCR for printed fields and fall back to the labelled replay if a model call fails.
**On-device measurement** (Andrew's M3 Pro, 18 GB; layout 1, 96 questions; `eval/results/ondevice_qwen7b/`):
83/96 correct: printed fields 48/48 (OCR), not-on-form 12/12 (abstained), B's ticks 10/12, "did A tick 8" 8/12,
sketch 5/12. Each model call takes ~9 s (median) and up to ~23 s, so the app shows a waiting line while it works.
Present the tick questions on-device; the sketch question is answered better by Haiku (live mode).

**Switching models live:** when Ollama is running, `./scripts/demo-live.sh` also offers the on-device model in a picker
(top right); each answer names the model that produced it ("answered by … · cloud API / on this laptop"), and
**Compare: ask the whole page instead** under a live answer sends the same question with the whole page to the same
model and shows both costs, token counts and times side by side (real calls; counts toward the spend threshold).
**Avoid empty tick lists live:** on forms where driver B ticked nothing (eas-004, eas3b-002), Haiku tends to decline
and the on-device Qwen once listed all 17 boxes. Use pairs where B ticked something (eas-002, eas3b-003: the tour's pairs).

## Presenting: the guided tour

Click **▶ Guided tour** (top bar). Each **Next ▶** performs one step of the judge script below (pick the form, ask,
switch to form b, then layout 3) and shows one sentence to say. Every answer also gets a plain-language line under
it ("Read on this computer by OCR from the printed line …", or "The form's own layout located … ; the model was sent
only that crop: ~N tokens instead of ~M for the whole page"). **What we measured** (top bar) opens the approved
results, each with its limits and the path of its receipt in the repository. It stays empty until the release
reviewer approves `docs/claims.json`.

## The two-minute judge script

1. In the **Fixture form** menu, choose **`eas-002 · pair: B's ticks differ`**.
   Form *a* opens. Form *b* is the same form with one of driver B's ticks moved (the menu does not say which).
2. Click the suggestion **"What is vehicle A's insurance policy number?"**
   You see the **LIVE OCR** badge, the policy number, a green box on it in the page, and the route
   `ocr → answer` at **$0**.
3. Click **"Which circumstance boxes did driver B tick?"**
   You see the **REPLAY** badge and the answer **8**. The route is `zoom anchor:ticks → answer`.
   Under the answer is the one image that would be sent to a model: the **anchor crop** (about 147×883 px),
   with the row numbers stitched next to driver B's tick column. On the page, a pink box marks the tick.
4. Click **form b** and ask the tick question again. The answer changes to **7** and the box moves one row up.
   The line above the page now shows `a: 8 · b: 7`; switching back to form a keeps its conversation.
   The policy number is still read by OCR, because only the tick differs.
5. Optional: click **"What is driver A's driving licence number?"** (not on the form). The route is
   `fallback page → zoom full page → abstain`: no anchor applies, so the full page would be sent, and the
   replayed answer is "not on the form". Type **"Is there a dog in the picture?"** and you get **NO ANSWER**
   with the reason: there is no stored answer to replay, so nothing is invented.

The **Session cost** panel compares this route with sending the full page to the same model every time,
with and without prompt caching. **All costs are estimates** from token arithmetic.

6. **A different layout.** In the menu, choose **`layout 3 (configured template) · eas3b-003`**. This form has a
   different design: stacked vehicle bands, values under their labels, bare row numbers, both tick columns left of
   the text. The built-in rules cannot read it; a short **configured template** (10 lines) can. Ask the policy
   number: **LIVE OCR**, route `ocr → answer`, and the answer says it came *from the line labelled "Policy No"*.
   Ask B's ticks: the template picks B's tick column (`zoom anchor:ticks`); form a has 3, 16 and form b has 2, 3.
   Optional: on **`layout 2 · eas2-001`** the policy number is *not* answered by OCR. Vision reads `J1-…` for
   `JI-…`, and the look-alike guard sends it to the page instead of risking a wrong ID.

## Measured, billed (OpenRouter receipts; synthetic forms)

- Accident statement, 96 questions: Haiku 5.5 on our route **96/96 for $0.0098**; Sonnet 5.5 on the cached whole
  page **96/96 for $0.2425** (24.7× lower API charge). Same model (Sonnet on both sides): $0.162 vs $0.243; the
  saving is the 48 questions OCR answers locally.
- Second configured layout, 12 new forms generated after the template was frozen: route **96/96 for $0.010**,
  original page 93/96 for $0.052 (Haiku on both sides).
- Five unconfigured layouts, 416 questions: all went to a full-page call; Haiku 401 through the router, 397 from
  the original page. The cost difference there comes from the page resolution, not routing.
- Total API spend for all experiments: about $1.50 of the $10 credit.

Sources and limits: `docs/NARRATIVE.md` §3. The app's session meter is a per-question **estimate**; the figures
above are receipts.

## What is real, what is replayed, what is estimated

| | status |
|---|---|
| OCR answers and their boxes | **real**: Apple Vision on your machine |
| routing decision, anchor selection, crop (or full page), box mapping | **real** code path |
| the vision model's reply (the answer and its box) | **replayed** from the test form's stored answer (`pipeline/visual/replay.py`) |
| token counts and $ | **estimated**, calibrated on billed usage (~width × height / 800 tokens per image, no downscale; list prices in `eval/pricing.py`) |

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
| `README.md`, `agent-messages/` | team dashboard and coordination log (background, not needed to run the demo) |

## Troubleshooting

- **Every answer is REPLAY or NO ANSWER, never LIVE OCR.** The OCR helper could not be built. Run
  `xcode-select --install`, then restart `./scripts/demo.sh`. OCR is macOS-only for now.
- **Port already in use.** Use `./scripts/demo.sh 8010`.
- **Uploading your own image.** It works, but visual questions get NO ANSWER, because there is no stored
  answer to replay without a live model. Text questions about a similar two-column form still go through OCR.
- **Start over.** Delete `.venv/` and rerun the script.
