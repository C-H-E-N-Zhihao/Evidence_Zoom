# breaker_panel

Home insurance: a photo-like view of an electrical distribution board (after a fire or water-damage claim, say). Circuit labels, ratings, installer and panel reference are printed text. Whether a breaker is ON or OFF shows only in the position of its toggle. The static "I"/"O" marks are printed on every breaker, so OCR text says nothing about switch state.

Regenerate from the repo root: `python3 -m eval.data.breaker_panel.generate` (fixed seed, deterministic).

## Templates
| | Template A (dev) | Template B (held-out) |
|---|---|---|
| Size | 2000 x 1350, landscape, no rotation | 1150 x 1650, portrait, rotated 0.9-1.6° |
| Layout | 2 rows x 6 vertical breakers + red main switch; printed label strip above each row | 1 column of 8 horizontal breakers; handwritten legend card to the right ("F1 ...") |
| ON / OFF | handle up / down (white handle in a dark slot) | handle right / left (orange handle) |
| Fonts | Helvetica / Arial Narrow | Georgia sticker, Noteworthy handwriting |

## Pairs
5 base panels (`bp-001`..`003` template A, `bp-004`..`005` template B), each with a partner `bp-XXXb`. Partners are pixel-identical except for ONE toggle: either the OFF breaker moves to another circuit (odd pairs), or a second breaker trips (even pairs). The change is recorded in `notes`.

## Questions (8 per image)
q1 installer (text), q2 panel ref (text), q3 rating printed on a named circuit's breaker (layout: label -> breaker), q4 circuit to the right of / below a named one (layout), q5 which breakers are OFF (visual, all orderings accepted), q6 is circuit X on or off (visual; X is the circuit that changes in the pair), q7 how many are OFF (visual), q8 unanswerable (e.g. the meter reading).

## Files and counts
- `items.jsonl`: all 80 items, 10 images. `items_dev.jsonl`: template A (48 items, 6 images). `items_heldout.jsonl`: template B (32 items, 4 images).
- By evidence type: text 20, layout 20, visual 30, unanswerable 10 (text, answer null).
