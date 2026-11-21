# Evidence Zoom: demo guide

**What it is.** A claims handler asks questions about an accident-statement form. The app answers and
**points to the evidence on the page**, while spending as little model compute as possible:

1. **OCR first.** If the answer is printed text (a policy number, a registration), local OCR reads it.
   This costs $0 and needs no model call.
2. **Look, then zoom.** If the answer needs pixels (which boxes are ticked, what the sketch shows), a vision
   model first sees a small overview with a grid. It then asks for just the cells it needs, cut from the
   original high-resolution page. Cells far apart on the same rows (a tick and its row number) are stitched
   side by side, so the crop stays small but keeps its meaning.
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

It runs four offline checks and ends with `ALL CHECKS PASSED`:

| check | what it proves |
|---|---|
| router unit checks | OCR → visual hand-off, error handling (stubbed stages) |
| visual path geometry | on 96 test questions, grid → selected cells → crop → box mapped back to the page lands exactly on the true evidence (IoU 1.0) |
| eval harness | the scoring code runs end to end |
| demo smoke test | the exact judge script below, through the app's HTTP API |

---

## The two-minute judge script

1. In the **Fixture form** menu, choose **`eas-002 · b: moved one of B's ticks from 8`**.
   Form *a* opens. Form *b* is the same form with one tick moved.
2. Click the suggestion **"What is vehicle A's insurance policy number?"**
   You see the **LIVE OCR** badge, the policy number, a green box on it in the page, and the route
   `ocr → answer` at **$0**.
3. Click **"Which circumstance boxes did driver B tick?"**
   You see the **REPLAY** badge and the answer **8**. The route is `fallback → overview → zoom → answer`.
   Under the answer are the two images that would be sent to a model: the gridded **overview** (434×536 px)
   and the **zoom mosaic**, with the row numbers stitched next to driver B's tick column. On the page, a pink
   box marks the tick.
4. Click **form b** and ask the tick question again. The answer changes to **7** and the box moves one row up.
   The policy number is still read by OCR, because only the tick differs.
5. Optional: type **"Is there a dog in the picture?"**. You get **NO ANSWER** and the reason. The demo never
   invents an answer.

The **Session cost** panel compares this route with sending the full page to the same model every time,
with and without prompt caching. **All costs are estimates** from token arithmetic.

## What is real, what is replayed, what is estimated

| | status |
|---|---|
| OCR answers and their boxes | **real**: Apple Vision on your machine |
| routing decision, overview image, cell selection, mosaic crop, box mapping | **real** code path |
| the vision model's two replies (which cells to zoom; the final answer and box) | **replayed** from the test form's stored answer (`pipeline/visual/replay.py`) |
| token counts and $ | **estimated** (~width × height / 750 tokens per image; list prices in `eval/pricing.py`) |

Measured so far, offline: OCR answers 48 of the 96 test questions, all correctly, in about 0.6 s, with 0 wrong
answers, also on degraded scans and photos. Model accuracy and billed savings need a live model run (see
`eval/results/SCORECARD.md`).

---

## Where things are

| path | what |
|---|---|
| `app/` | web app (FastAPI + one HTML page): `server.py`, `static/` |
| `pipeline/router.py` | OCR first, then the visual path |
| `pipeline/ocr/` | OCR route (Apple Vision helper + field lookup) |
| `pipeline/visual/` | overview grid → mosaic zoom → grounded answer; `replay.py` = key-free stand-in for the model |
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
