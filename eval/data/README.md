# Eval data

One folder per set: `eval/data/<set>/items.jsonl` plus its images. One `EvalItem` (see `eval/schema.py`) per line:

```json
{"question_id": "eas-001-q2", "image_id": "eas-001", "image_path": "images/eas-001.png",
 "question": "Which circumstance boxes did driver B tick?", "answer": "8",
 "answerable": true, "evidence_type": "visual", "evidence_boxes": [[0.62, 0.31, 0.70, 0.74]],
 "accepted_answers": ["box 8", "circumstance 8"], "pair_id": "eas-001", "source": "synthetic"}
```

- Boxes: `[x0, y0, x1, y1]`, normalized 0–1 on the original image, origin top-left.
- `evidence_type`: `text` (OCR suffices), `layout` (needs position/structure), `visual` (pixels only, e.g. ticks), `mixed`.
- Unanswerable items: `answer: null`, `answerable: false`, no boxes. Correct behaviour is to abstain.
- Counterfactual pairs share `pair_id` (same form, one changed tick/value).
- Group questions about one image consecutively; the cost curve and caching depend on it.
- Keep large or real (non-public) images out of git; commit only the synthetic set and the generator.

## Sets

- `demo_sample/`: 8 questions on `app/static/sample.png`, **generated** by `python -m app.make_sample` (same renderer and templates as `accident_statement`, seed 2: A ticks 8,9; B ticks 10,16). Gold labels are regenerated together with the image, so they cannot drift. A smoke test, not an evaluation.
- `accident_statement/`: `python -m eval.data.accident_statement.generate`; 6 forms + 6 counterfactual partners, 8 questions each (96 items).
