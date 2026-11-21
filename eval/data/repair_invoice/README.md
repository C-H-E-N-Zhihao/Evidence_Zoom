# repair_invoice

Motor claims: a garage repair invoice sent to the insurer. Line items, totals and references are printed text. Which payment option is marked, and whether a rotated ink stamp is present, show only in pixels. The stamp's word is printed in the stamp area's caption on every invoice ("For office use (PAID stamp)" / "Insurer stamp (APPROVED / REJECTED)"), so finding the word in OCR output does not show that a stamp is present.

Regenerate from the repo root: `python3 -m eval.data.repair_invoice.generate` (fixed seed, deterministic).

## Templates
| | Template A (dev) | Template B (held-out) |
|---|---|---|
| Size | 1500 x 2120, A4 portrait, no rotation | 1900 x 1250, landscape, rotated about 1.2-1.4° |
| Layout | logo + meta block; table Pos / Description / Qty / Unit price / Amount; totals under the table | dark header band; details and totals in the left column; table Code / Description / Qty / Amount in the right column |
| Payment mark | hand-drawn tick in one of 3 checkboxes | hand-drawn ellipse around CASH / CARD / TRANSFER |
| Stamp | red rectangular "PAID" + date, rotated 17°, semi-transparent | round blue "APPROVED" insurer stamp, rotated -12° |
| Fonts | Helvetica | Courier New (mono) + Georgia |

## Pairs
5 base invoices (`inv-001`..`003` template A, `inv-004`..`005` template B), each with a partner `inv-XXXb` identical except for ONE detail: the stamp is added or removed (pairs 1, 3, 5), or the payment mark moves to another option (pairs 2, 4).

## Questions (8 per image)
q1 invoice number (text), q2 vehicle plate (text), q3 amount of a named line (layout: row alignment), q4 line item directly below a named one (layout), q5 total incl. VAT (text), q6 which payment option is marked (visual), q7 is the stamp present (visual; for "no" the gold box is the empty stamp area), q8 unanswerable (e.g. the mechanic's name, IBAN, mileage).

## Files and counts
- `items.jsonl`: 80 items, 10 images. `items_dev.jsonl`: template A (48 items). `items_heldout.jsonl`: template B (32 items).
- By evidence type: text 30, layout 20, visual 20, unanswerable 10.
