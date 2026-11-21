# accident_statement_v3

Third, independent synthetic layout of the European Accident Statement. 6 forms + 6 counterfactual partners
(12 images), 8 questions each (96 items). Generate: `python3 -m eval.data.accident_statement_v3.generate`
(macOS fonts: Palatino, Optima, Courier). Check: `shasum -a 256 -c images.sha256` from this folder. Images are git-ignored.

## Layout (A4 portrait, 1650x2340)
- Dark-blue header band with title and form reference; footer with two signature lines.
- Vehicles stacked as two full-width coloured bands (A blue, B orange), each with a coloured letter tab and a 2x2 field grid:
  "Insurance company", "Policy No", "Licence plate", "Name of driver" (values in Courier/Palatino on underlined lines).
- Section order: vehicles, then "13. Sketch of the accident", then "12. Circumstances" (13 before 12).
- Sketch: grey two-lane road, dashed centre line; two rounded rectangles A and B one behind the other in the right lane, a direction-of-travel arrow beside them.
- Circumstances: 17 rows, columns left to right: A box, B box, row number, text (both tick columns left of the text, B right after A); header row, zebra stripes, ticks drawn as X.
- Pairs 1-4: one of B's ticks added/moved. Pairs 5-6: sketch roles swapped (which vehicle is in front).
- Gold boxes recorded at draw time. Q4 gold = B's ticked boxes plus their row-number labels (whole B column if none).

## Blindness
Written without reading `pipeline/`, `bench/`, `eval/data/accident_statement/generate.py`, the v2 images, any existing set image, or `eval/results/`. Read only `eval/schema.py`, `eval/data/README.md`, `eval/run_eval.py` (argument parsing), and the first lines of the original `items.jsonl` for the question format. All names, plates, policy numbers are invented. Seed 3003.
