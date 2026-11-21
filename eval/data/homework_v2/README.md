# homework_v2

Held-out synthetic test set for the general vision assistant (study/school images). 96 items over 12 images
(6 page kinds, each an `a`/`b` pair differing in 1-3 visual details that flip the gold answer of the visual questions).

Page kinds: science lab (table + line graph), geography quiz (drawn map, compass, star, key), fractions page with
handwritten student answers and teacher ticks/crosses, vocabulary matching with drawn lines, weekly timetable
(highlighted cell, shaded column, star sticker), geometry (right-angle marker, red dot, shaded crossing-line angle).
Sizes and fonts vary (2200x1500, 1700x2200, 2000x1500, 1800x2000).

Generate: `python3 -m eval.data.homework_v2.generate` (env `HW2_SEED`=9091, `HW2_OUT`=package dir). Images go to
`images/` (git-ignored); `items.jsonl` has the eval item fields. Deterministic given the seed.

Written blind by a subagent: it did not read `pipeline/`, `eval/data/homework_v1/`, `eval/results/` or `agent-messages/`.

Counts (evidence_type): text 32 answerable + 12 unanswerable (type "text", answer null, no boxes), mixed 20, visual 32.
The same question text is used for `a` and `b`; gold answers differ on visual/mixed ones.
Scoring caveat: metrics.py matches golds by word-boundary containment, so single-letter golds ("A", "B") are lenient.
