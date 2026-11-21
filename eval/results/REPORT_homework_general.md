# General assistant route on homework sheets (OCR text first, pixels only when asked)

Run `eval/results/homework_haiku/run_20261121-214700.json`. Model `or:anthropic/claude-haiku-5.5` for both arms.
80 questions on 10 synthetic sheets (`eval/data/homework_v1`). Spend $0.0665, under the $0.15 cap. Owner: claude-andrew-b.
The route, the dataset and this report are by the same agent, so this needs an independent review before any claim is made (per §3).

| | general route (OCR text, then a crop if asked) | whole page, same model |
|---|---|---|
| accuracy (strict scorer) | 79/80 | 80/80 |
| evidence hit@0.3 | 94% | 76% |
| cost per question | $0.00031 | $0.00052 |
| median latency | 2.3 s | 1.5 s |
| answered without sending any image | 32/80 | 0/80 |
| unanswerable questions abstained | 10/10 | 10/10 |

The one strict miss: `hw-004b-q6`, where the route answered "June" and the answer key says "Jun". The gold set was left unchanged after seeing the result.

Per question (10 each, cost per question):

| question | type | route: sent an image | route accuracy | route cost | page cost |
|---|---|---|---|---|---|
| q1 solve the equation | text | 0/10 | 10/10 | $0.00012 | $0.00053 |
| q2 year in the passage | text | 0/10 | 10/10 | $0.00008 | $0.00049 |
| q3 deck replaced with | text | 0/10 | 10/10 | $0.00011 | $0.00050 |
| q4 hypotenuse | mixed | 8/10 | 10/10 | $0.00049 | $0.00056 |
| q5 circled letter | visual | 10/10 | 10/10 | $0.00035 | $0.00050 |
| q6 tallest bar | visual | 10/10 | 9/10 (strict) | $0.00038 | $0.00050 |
| q7 is the circled answer right | visual | 10/10 | 10/10 | $0.00043 | $0.00058 |
| q8 teacher's grade (absent) | unanswerable | 10/10 | 10/10 abstain | $0.00055 | $0.00049 |

Against the predictions in message 145:
- **Met.** Text questions: 30/30 answered from OCR text alone, at about 1/5 of the page cost.
- **Met.** Visual questions: every one asked for pixels, so OCR text did not pass for a circle or a bar. 29/30 strict, 30/30 if "June" counts as "Jun".
- **Met.** Unanswerable: 10/10 abstained.
- **Worse than wished.** For the missing teacher's grade, the text step always asked for the image, since a grade could be a handwritten mark that OCR missed. That makes it the one question type where the route costs more than the page. This is defensible behaviour and has not been tuned.
- Pair metric (all 16 questions of a worksheet pair right): route 4/5 and page 5/5. The route's failed pair is hw-004, the strict "June" miss.

Limits: synthetic, clean renders, one seed, built by the route's author, with Pillow 11 renders. This shows the mechanism works (text answered without pixels, pixels requested when needed), not a general accuracy figure.
