# vehicle_damage

Motor claims: an inspector's damage sheet with a printed car outline. Claim data are typed. Panel numbers or letters and their names are printed (key table), and every panel name is in the key on every sheet. Which panels are damaged, and how, exists only as drawn marks on the diagram.

Regenerate from the repo root: `python3 -m eval.data.vehicle_damage.generate` (fixed seed, deterministic).

## Templates
| | Template A (dev) | Template B (held-out) |
|---|---|---|
| Size | 1500 x 2000, portrait, no rotation | 2000 x 1250, landscape, rotated about 1.2-1.3° |
| Diagram | top view, 15 numbered panels (glass panels tinted), key table on the right | left- and right-side profiles, 12 lettered zones (A-F left, G-L right), key below |
| Marks | red "X" = scratch, red hatching = dent | red filled dot = dent, red zig-zag = scratch |
| Fonts | Helvetica | Arial Narrow + Georgia |

## Pairs
5 base sheets (`dmg-001`..`003` template A, `dmg-004`..`005` template B), each with 2 damaged panels and a partner `dmg-XXXb` identical except for ONE detail: one mark moves to another panel (pairs 1, 3, 5), or one mark changes type, scratch <-> dent (pairs 2, 4).

## Questions (8 per image)
q1 claim number (text), q2 plate (text), q3 odometer (text), q4 which panel has number N / letter X (layout: key lookup), q5 which panels are marked damaged (visual; gold boxes = panel + its key row; all orderings accepted), q6 damage type on a named panel (visual), q7 is a named panel damaged (visual; in move pairs this is the panel the mark moves to), q8 unanswerable (e.g. repair cost, VIN, colour).

## Files and counts
- `items.jsonl`: 80 items, 10 images. `items_dev.jsonl`: template A (48 items). `items_heldout.jsonl`: template B (32 items).
- By evidence type: text 30, layout 10, visual 30, unanswerable 10.
