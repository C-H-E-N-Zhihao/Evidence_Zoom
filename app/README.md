# app/ — Evidence Zoom demo (owner: claude-zhihao)

FastAPI backend + single-page frontend. Runs against a **mock pipeline** until
the real OCR / overview / zoom pipeline exists. Answers from the mock are fake.

```bash
python3 -m venv .venv && .venv/bin/pip install -r app/requirements.txt
.venv/bin/python -m app.make_sample        # renders app/static/sample.png
.venv/bin/uvicorn app.server:app --port 8000
```

Plug in a real pipeline: `PIPELINE=pipeline.router .venv/bin/uvicorn app.server:app`.
The module must expose `answer(image: PIL.Image.Image, question: str) -> Result`
(see `app/schema.py`, draft in agent-messages/2026-11-21-008).

- `POST /api/images` (multipart `file`) / `POST /api/images/sample` → `{image_id, width, height, url}`
- `POST /api/ask {image_id, question}` → `{result, baseline, question_index, pipeline}`
  where `baseline` is the **estimated** cost of sending the full image (uncached
  and with prompt caching) for the same question, used by the cost meter.

UI: upload/demo form, 4×4 labelled grid overlay, zoomed cell + evidence boxes
per answer, route chips (ocr → overview → zoom B3 → answer), and a session cost
meter comparing Evidence Zoom with full-image (cached / uncached).

All prices and image-token counts in `app/costs.py` are unverified estimates.

## Key-free judge rehearsal

```bash
./scripts/demo.sh            # http://localhost:8000 ; first run creates .venv and installs deps
```

Runs `PIPELINE=pipeline.router DEMO_REPLAY=1`. Pick a fixture pair (`eas-002` / `eas-006`: B's tick moves
between form a and b; `eas-005`: a tick is added; others swap the sketch roles) and click the suggested
questions. Every answer carries a source badge:

- **LIVE OCR**: answered on this machine by Apple Vision OCR (macOS), $0, evidence box from the OCR span.
- **REPLAY**: the real router → overview → zoom → box-mapping code runs; only the vision-model replies are
  replayed from the fixture's gold labels (`pipeline/visual/replay.py`). The images actually sent at each
  step are shown under the answer (overview with grid, row-aligned mosaic crop). Tokens and cost are estimates.
- **NO ANSWER**: a stage was unavailable (e.g. a question with no fixture label); nothing is invented.

Rehearsal check: on `eas-002`, "Which circumstance boxes did driver B tick?" answers 8 on form a and 7 on
form b, with the box on the right row of the original page; the policy-number question is LIVE OCR on both.
