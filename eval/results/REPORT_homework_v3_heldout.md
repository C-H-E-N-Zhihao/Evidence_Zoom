# General assistant, second held-out set (homework_v3): fix 1 matches the whole page at 69% of the cost

Run `eval/results/homework_v3_haiku/run_20261121-224427.json`. Code at tag `freeze-general-v2` (1df5104); the run commit 9a88b0d adds only the dataset; `pipeline_dirty: false`.
Model `or:anthropic/claude-haiku-5.5` on both arms. Spend $0.0805 (cap $0.15), plus a $0.0012 two-question smoke test.
Protocol: messages 150 and 151. Predictions were committed in 151 before the set existed.
Dataset `eval/data/homework_v3` was written by a fresh Sonnet subagent that read none of `pipeline/`, homework_v1/v2, `eval/results` or the board. One slip: an `ls eval/data` showed the sibling folder names, and none were opened.
It has 6 new page kinds: recipe card with measuring jug, circuit with switches, pie chart, calendar with marks, bubble answer sheet, labelled plant diagram. Drawings sit above, beside and below their text. a/b pairs, 96 questions.
The images were committed (`images.sha256`) without opening them before the run. I wrote the subagent's brief, and fix 1 was designed after homework_v2 failures, not on this set.

| | general route (fix 1) | whole page, same model |
|---|---|---|
| accuracy | **96/96** | **95/96** |
| text (36 answerable + 12 unanswerable) | 48/48 | 48/48 |
| mixed | 18/18 | 17/18 |
| visual | 30/30 | 30/30 |
| cost total / per question | $0.0330 / $0.00034 | $0.0475 / $0.00049 |
| text questions answered with no image | 44/48 | 0/48 |
| band crop not enough, escalated to the page | 2/96 | n/a |
| unanswerable abstained | 12/12 | 12/12 |

Predictions (message 151) against the result:
- **Met.** The route sends no image on at least 90% of text questions and scores within 2 of the page: 44/48 = 92%, and 48 vs 48.
- **Met.** Overall within 3 of the page: 96 vs 95.
- **Met.** Route cost at most 80% of the page: 69%.
- **Met.** Both arms abstain on at least 80% of unanswerable questions: 12/12 each.

Limits:
- Synthetic, clean renders, one seed, one model.
- The scorer matches word-boundary substrings, so single-token answers ("A", "No", "3") are lenient for both arms. The subagent flagged this.
- Ceiling effect: both arms are near 100%, so this shows the route does not lose accuracy on these 6 page kinds. It does not show the route is more accurate.
- The earlier held-out set (homework_v2, before fix 1) had route 83/96 vs page 94/96. That result stands as history, and fix 1 was designed from its failures.
- Same agent for the route and the brief: needs independent review (§3).
