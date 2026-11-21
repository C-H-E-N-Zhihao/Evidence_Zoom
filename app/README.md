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
