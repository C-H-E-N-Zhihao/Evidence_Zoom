# General assistant, held-out worksheets (homework_v2): the route loses 11 points to the whole page

Run `eval/results/homework_v2_haiku/run_20261121-221826.json`, code at tag `freeze-general-v1` (54d6b96; run commit eddbbd7 adds only the dataset; `pipeline_dirty: false`).
Model `or:anthropic/claude-haiku-5.5` for both arms. Spend $0.0809, cap $0.15.
Dataset `eval/data/homework_v2`: 6 page kinds (lab table and graph, map, marked fractions, matching lines, timetable, geometry), in a/b pairs, 96 questions.
It was written by a Sonnet subagent that did not read `pipeline/` or homework_v1. I wrote its brief, so it is not independent of me.

| | general route | whole page, same model |
|---|---|---|
| accuracy | **83/96 (86%)** | **94/96 (98%)** |
| text (incl. 12 unanswerable) | 41/44 | 42/44 |
| mixed | 17/20 | 20/20 |
| visual | 25/32 | 32/32 |
| cost per question | $0.00033 | $0.00051 |
| answered with no image sent | 50/96 | 0/96 |

On homework_v1 (development data) the route was 79/80 and the page 80/80. **The held-out set does not support "same accuracy at lower cost" for the general route.**

Why the route lost (13 misses; both arms share the 2 "score" misses):

1. **The crop band misses the evidence (5 misses, the main cause).** After the text step names the nearest lines, the route crops from just above the first named line to 0.30 of the page below the last one. That assumes the drawing sits under its text, as it does on homework_v1. On these pages the named lines are often the axis labels, a legend or a key *below* the drawing, so the band missed the graph (001b q5, q6, q7), the highlighted timetable cell (005b q5) and most of a matching line (004b q6). The model then correctly abstained.
2. **The text step abstains when it should ask for the image (2 misses).** "What is the missing value in the table?" (001a/001b q4): the OCR text cannot show which cell is empty, and the model abstained instead of asking for pixels.
3. **A visual question answered from OCR text (1 miss).** 003a q6 "tick or cross next to question 6": the model reasoned over OCR glyphs (a tick read as "V") and answered without the image, despite the prompt.
4. **Counting in the crop (2 misses).** Mountain symbols in a map region: 0 vs 3 and 2 vs 5. The band did not cover the region's top.
5. **Truncated JSON shown as the answer (1 miss; also a display bug).** 003b q8: a long explanation and line list hit the output limit, JSON parsing failed, and the raw JSON became the answer. OCR had also read "/ 8" as "18".
6. **Unanswerable item answered (1 miss).** 001b q8 "room temperature" was answered "20 °C" after the crop. That is a hallucination or a reading of the time-0 value.
7. **Gold disputed on both arms.** "What score did the student get?" has a blank score line, but both arms counted the ticks (5/8). That is a reasonable reading, and the item is arguably mis-specified.

What this means for the demo: the general assistant shows the mechanism (text questions answered with no image at about 40% of the page cost, 41/44 text). Do not claim accuracy parity on visual questions; on this set it is 25/32 vs 32/32.

Fixes (2, 3, 5 and a "band, then whole page" escalation for 1 and 4) are next. After them homework_v2 becomes development data, and a third blind set is needed for any new held-out claim.
