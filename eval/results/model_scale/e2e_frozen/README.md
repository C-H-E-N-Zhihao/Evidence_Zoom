# End to end on the HELD-OUT layout v2, and the development layout, from the frozen code

**Provenance.** Run from a git worktree checked out at tag `freeze-anchor-ocr-v1` = `0b2a138`. `pipeline/` tree
`a989fe9d2211` = frozen tag, no local changes (`git status pipeline` empty). The harness in that worktree predates
the automatic `meta.pipeline_equals_freeze` field (058), so provenance is stated here; run JSON `meta.commit` = 0b2a138.
The held-out data (`eval/data/accident_statement_v2`, 3e9f2f8) was copied in unchanged. Command: `run_heldout.sh` (this
folder). Qwen2.5-VL-7B-Instruct (A100) and Qwen2.5-VL-72B-Instruct-AWQ (H100), local vLLM on RCP, $0.
Route = `cascade:fn:pipeline.ocr:answer|pipeline.anchor:factory_then_overview` (OCR → anchor crop → overview → zoom).

| layout | model | route | full page | missing field (q7) answered with an invented value: route / page |
|---|---|---:|---:|---|
| **held-out v2** | 7B | **35/96** | 72/96 | **12/12** / 5/12 |
| **held-out v2** | 72B | **50/96** | **91/96** | 5/12 / 0/12 |
| development v1 | 7B | 84/96 | 75/96 (`../e2e`, b42ece9) | 1/12 / 0/12 (corrected: 2/12 was the b42ece9 route, judge 063) |
| development v1 | 72B | 93/96 | 80/96 (`../e2e`, b42ece9) | 0/12 / 0/12 |

Per evidence type, held-out v2: 7B route text 14/48 · layout 12/12 · visual 9/36 (page 43 · 12 · 17); 72B route text 27/48 ·
layout 12/12 · visual 11/36 (page 48 · 12 · 31). ("text" includes the 12 unanswerable q7.)

## Reading

1. **On an unseen layout the route is much worse than the full page** (7B 35 vs 72, 72B 50 vs 91). OCR and the anchor
   decline every question (andrew-b's stage reports, 059/061), so everything goes to the **overview → model-chosen zoom**
   fallback, which `../README.md` already showed cannot select the evidence (0/24, 3/36). Text questions now face a
   512-px thumbnail.
2. **The overview fallback makes models invent values**: the 7B route invents a licence number on all 12 missing-field
   questions (the page: 5/12); 72B route 5/12 (the page: 0/12). Unreadable input pushes models toward guessing.
3. Development v1 at the frozen code (after 055's q5 note): 7B 84/96, 72B 93/96. Per the judge (057), this is **after a
   fix informed by test errors**; the clean pre-fix numbers are `../e2e` (79/96, 95/96).

## Design consequence (policy, not tuning)

When the local stages decline, the fallback should be **the full page**, not the overview zoom. With that policy the
held-out numbers become the full-page numbers by construction (72/96 and 91/96, at full-page cost), and the development
numbers change only on the few questions the anchor does not cover. No further GPU run is needed to know this.
`pipeline/router.py` is frozen (056); the change belongs to a new, labelled configuration after the freeze is lifted.
