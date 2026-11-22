# app/ — Evidence Zoom demo (owner: claude-andrew-b, from claude-zhihao, message 070)

FastAPI backend + single-page frontend. Default pipeline is a **mock** (fake answers); the demo runs
`PIPELINE=pipeline.router` (router@v2: OCR answer → template-anchored crop → full-page fallback).

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

UI: upload/demo form, evidence boxes per answer, the image actually sent (anchor crop or full page),
route chips (e.g. `ocr → answer`, `zoom anchor:ticks → answer`, `fallback page → zoom full page → abstain`),
and a session cost meter comparing Evidence Zoom with full-image (cached / uncached).

All prices and image-token counts in `app/costs.py` are unverified estimates.

## Key-free judge rehearsal

```bash
./scripts/demo.sh            # http://localhost:8000 ; first run creates .venv and installs deps
```

Runs `PIPELINE=pipeline.router DEMO_REPLAY=1`. Pick a fixture pair (`eas-002` / `eas-006`: B's tick moves
between form a and b; `eas-005`: a tick is added; others swap the sketch roles) and click the suggested
questions. Every answer carries a source badge:

- **LIVE OCR**: answered on this machine by Apple Vision OCR (macOS), $0, evidence box from the OCR span.
- **REPLAY**: the real router@v2 runs (OCR → template-anchored crop → full-page fallback) and the real box
  mapping; only the vision-model reply is replayed from the fixture's gold labels (`pipeline/visual/replay.py`).
  The image actually sent is shown under the answer: the row-aligned anchor crop (e.g. B's tick column next to
  the row numbers) or, when no anchor applies, the full page. Tokens and cost are estimates.
  On a machine without the macOS OCR helper there is no OCR answer and no anchor, so every visual question
  shows `zoom full page`.
- **NO ANSWER**: a stage was unavailable (e.g. a question with no fixture label); nothing is invented.

Rehearsal check: on `eas-002`, the suggested question "Which circumstance boxes did driver B tick? Answer with
the box numbers." answers 8 on form a and 7 on form b via `zoom anchor:ticks` (macOS), with the box on the
right row of the original page; the policy-number question is LIVE OCR on both; "What is driver A's driving
licence number?" takes `fallback page → zoom full page → abstain` (not on the form).

## Live demo (release check C1)

Visual questions go to a real model on the crop (or, when no template applies, the page cropped to its OCR text area and downscaled):

```bash
export OPENROUTER_API_KEY=...   # from the key holder, in your shell only; never commit it or paste it in a message
DEMO_LIVE=1 DEMO_REPLAY=1 EVAL_MODEL=or:anthropic/claude-haiku-5.5 PIPELINE=pipeline.router \
  .venv/bin/uvicorn app.server:app --port 8000
```

- Badges: **LIVE OCR** (local, $0), **MODEL** (a real, billed call to `EVAL_MODEL`), **REPLAY** only if a live
  call fails and `DEMO_REPLAY=1` is set (the failure reason is shown under the answer), **NO ANSWER** otherwise.
- The cost meter prices the full-page baseline with `APP_MODEL` (default Sonnet 5.5); model answers carry the
  provider's billed cost.
- Tested offline with a fake OpenAI-compatible server (`EVAL_MODEL=local:… OPENAI_BASE_URL=…`): live answer →
  MODEL; endpoint down + `DEMO_REPLAY=1` → REPLAY with the error; endpoint down alone → NO ANSWER.

