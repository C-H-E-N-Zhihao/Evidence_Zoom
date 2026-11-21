# pipeline/visual — overview → zoom → grounded answer (owner: claude-zhihao)

`answer(image, question, prior=None, **cfg) -> eval.schema.PipelineResult`

1. **Overview**: the page downscaled to 512 px (long side) with a faint 8×6 grid; row labels R1…R8 in the
   left margin, column labels C1…C6 in the top margin (no label covers content).
   The model answers, or asks to zoom on a list of cells.
2. **Zoom**: the selected cells are cropped from the ORIGINAL pixels. Cells need not be adjacent:
   the selection becomes *row bands × column bands*, stitched with grey separators, **row-aligned**.
   Example: "which boxes did driver B tick?" → label column + B's tick column over the same rows:
   ~415 image tokens instead of ~1530 for the page, and the crop still shows which row each tick is on.
   (A plain contiguous crop of B's column showed ticks but not their numbers.)
3. Boxes the model gives on any view (padded overview, mosaic) are mapped back to the original image;
   a box spanning several bands yields one evidence box per band.

Each step is a fresh single-turn call; the zoom call gets the overview's `look_for` note, not the overview
image. With `max_zooms ≥ 2` a crop carries a 2×2 sub-grid and can be refined again.

Eval: `--pipelines pipeline.visual:factory | :factory_cheap_overview | :factory_two_zooms`, or end to end
`pipeline.router:factory` (OCR first). App: `PIPELINE=pipeline.router uvicorn app.server:app`.

Offline check, $0: `python -m pipeline.visual.selftest [--router] [--save-views DIR]` runs the full geometry
with an oracle backend (asks for the gold cells, answers with the gold box). Expect acc 1.0, IoU 1.0 on the
visual items. Token counts there are estimates.
