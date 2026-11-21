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

This branch runs **without any API key**. OCR is real. The vision model's replies are **replayed** from the
answers stored with each test form, and every replayed answer is labelled as such.

---

## Run it (macOS, about 2 minutes the first time)

```bash
git clone -b demo/human-readable git@github.com:Andrew1207-Yang/LauzHack.git evidence-zoom
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
| eval harness | ~40 unit checks on scoring, pricing and guards, plus an end-to-end run |
| demo smoke test | the exact judge script below, through the app's HTTP API |

---

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

## What is real, what is replayed, what is estimated

| | status |
|---|---|
| OCR answers and their boxes | **real**: Apple Vision on your machine |
| routing decision, anchor selection, crop (or full page), box mapping | **real** code path |
| the vision model's reply (the answer and its box) | **replayed** from the test form's stored answer (`pipeline/visual/replay.py`) |
| token counts and $ | **estimated** (~width × height / 750 tokens per image; list prices in `eval/pricing.py`) |

Measured results, their limits and their provenance are in `docs/NARRATIVE.md` (the reviewed source for any
number you quote). In short: on this one form template, OCR answers the printed fields locally and the
template-anchored crop lets a small model answer the visual questions; on an unseen layout and on other
document types the anchors find nothing and the page fallback applies.

---

## Where things are

| path | what |
|---|---|
| `app/` | web app (FastAPI + one HTML page): `server.py`, `static/` |
| `pipeline/router.py` | router@v2: OCR answer → anchored crop (`pipeline/anchor/`) → full-page fallback |
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
