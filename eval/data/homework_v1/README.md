# homework_v1: synthetic homework sheets (general assistant route)

5 worksheets plus a partner for each (the circled option and the tallest bar move): 10 images, 80 questions.
Question types: text (equation, passage fact, passage inference), mixed (triangle hypotenuse), visual (circled
option, tallest bar, "is the circled answer correct"), unanswerable (teacher's grade). Gold boxes are recorded at draw time.

Images are not committed. Regenerate with `python -m eval.data.homework_v1.generate` (seed `HW_SEED=4242`).
`images.sha256` holds the hashes of the images used in the billed run `eval/results/homework_haiku/`, rendered with
**Pillow 11.0.0**. Other Pillow versions anti-alias text differently, so the PNG bytes differ (the venv's Pillow 13 does),
but `items.jsonl` (questions, answers, gold boxes) is byte-identical.

Built after the general route was designed, by the same agent (claude-andrew-b). It is a smoke-scale test, not a
held-out benchmark.
