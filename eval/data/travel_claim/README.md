# travel_claim

Travel insurance: a claim for medical expenses abroad. Personal data and the expenses table are typed. The description of events is handwriting (still text, but harder OCR). The yes/no health answers and the declaration signature exist only as pen marks. Every question text and every "Yes"/"No" caption is printed for all questions, so OCR text cannot tell which answer was marked.

Regenerate from the repo root: `python3 -m eval.data.travel_claim.generate` (fixed seed, deterministic).

## Templates
| | Template A (dev) | Template B (held-out) |
|---|---|---|
| Size | 1400 x 1980, A4 portrait, no rotation | 2000 x 1400, landscape, rotated about 1.1-1.5° |
| Layout | 5 numbered sections stacked; questionnaire is a ruled table (No. / Question / Yes / No columns) | two columns: personal data, expenses and description on the left; numbered questions with inline radio circles, plus signature, on the right |
| Answer mark | hand-drawn cross in a square box | pen-filled circle |
| Fonts | Helvetica; Noteworthy handwriting | Georgia + Courier values; Bradley Hand handwriting |

## Pairs
5 base forms (`clm-001`..`003` template A, `clm-004`..`005` template B), each with a partner `clm-XXXb` identical except for ONE detail: one questionnaire answer flips yes <-> no (pairs 1, 3, 4), or the signature is added or removed (pairs 2, 5).

## Questions (8 per image)
q1 policy number (text), q2 insured person (text), q3 amount for a named expense (layout), q4 city named in the handwritten description (text, handwriting), q5 answer to question N (visual; N is the flipped question in answer-flip pairs), q6 which questions were answered Yes (visual, all orderings accepted, "none" if none), q7 is the declaration signed (visual), q8 unanswerable (e.g. treating doctor, diagnosis).

## Files and counts
- `items.jsonl`: 80 items, 10 images. `items_dev.jsonl`: template A (48 items). `items_heldout.jsonl`: template B (32 items).
- By evidence type: text 30, layout 10, visual 30, unanswerable 10.
