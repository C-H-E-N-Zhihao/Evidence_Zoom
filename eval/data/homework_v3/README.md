# homework_v3 (synthetic, held-out)

96 items: 6 page kinds x 2 variants (a/b) x 8 questions. Test set for the general vision assistant.

Page kinds: (1) recipe card + drawn measuring jug, (2) circuit worksheet (battery, lamps, open/closed switches),
(3) class-survey pie chart with legend + paragraph, (4) calendar month with circled/crossed/highlighted days and printed events,
(5) multiple-choice bubble sheet with a printed answer key box, (6) textbook page with labelled plant diagram, paragraph and exercise.
Pages differ in size/orientation (portrait and landscape), fonts, colours and where the drawing sits relative to its text.

Each pair (`hw3-00Na` / `hw3-00Nb`, `pair_id` `hw3-00N`) shares all printed content and differs in 1-2 drawn details
(jug fill level; which switch is open; which pie slices are largest; which day is circled/highlighted; which bubbles are filled;
which label an arrow points to + petal colour). Per page: 3 text, 1-2 mixed, 2-3 visual, 1 unanswerable (information truly absent).

## Run
    python3 -m eval.data.homework_v3.generate        # env: HW3_SEED (default 50505), HW3_OUT (default: this directory)
Writes `images/*.png` (git-ignored) and `items.jsonl`. Deterministic for a seed (Pillow, system fonts from
/System/Library/Fonts/Supplemental). Evidence boxes are recorded at draw time, normalised [x0,y0,x1,y1].

## Counts (seed 50505)
evidence_type: text 48 (36 answerable + 12 unanswerable), mixed 18, visual 30. Unanswerable: 12 (answerable=false, answer null, no boxes).

## Blind authorship
Written without opening anything under `pipeline/`, `eval/data/homework_v1/`, `eval/data/homework_v2/`, `eval/results/`,
`agent-messages/`, nor DEMO.md or docs/. Only `eval/schema.py` and the scoring part of `eval/metrics.py` were read.
Excluded kinds (by instruction): lab table+line graph, map, fraction/tick worksheet, vocabulary matching, weekly timetable, geometry triangle,
and the generic equation + passage + circled-MC + bar chart worksheet.

## Caveats
Scoring is word-boundary substring match on normalised answers, so single-letter/number golds ("A", "No", "3") can match a longer wrong answer containing that word.
