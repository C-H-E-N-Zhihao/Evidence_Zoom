# Can the app find evidence in a real phone photo?

On **64 mobile photos of Vietnamese receipts**, the shipped accident-form OCR and anchor stages declined every eligible date and total question (112/112). The existing app would continue to its visual fallback. We measured the local stages only. A new, **benchmark-only** selector using OCR spans generalized to receipt dates more readily than payable totals. Even an exact numeric answer sometimes pointed to a different printed line.

## Results

The first 32 photos formed the pilot. We froze one change after inspecting that cohort: give explicit final-payment labels priority over generic total labels. The next 32 previously unopened photos tested both rules. The date rule stayed fixed.

| Cohort and selector | Eligible | Covered / partial / missed / declined | Correct from selected crop | Correct from annotated crop | Correct **and** covered |
|---|---:|---:|---:|---:|---:|
| Pilot · date | 30 | 22 / 5 / 0 / 3 | 27 | 27 | 22 |
| Pilot · total | 25 | 12 / 3 / 6 / 4 | 19 | 25 | 12 |
| Held-out · date | 31 | 28 / 3 / 0 / 0 | 31 | 30 | 28 |
| Held-out · total, pilot rule | 26 | 3 / 4 / 5 / 14 | 10 | 25 | 3 |
| Held-out · total, final-payment priority | 26 | **7 / 4 / 1 / 14** | **10** | **25** | **6** |

The change moved four held-out total crops from a missed annotation to full coverage. All four kept their previous answer score: three already returned the annotated number at another location, and the fourth still misread the number. Giving OCR the annotated crop recovered 25/26 held-out totals; the revised selector plus the same OCR recovered 10/26. Fourteen questions lacked a unique selection. This is where better routing or an explicit fallback could help. For dates, a selected crop can read more cleanly than the annotated line because the boxes differ in context. The annotated-crop result is a reference, not an accuracy ceiling.

**Two cases for the demo.** On pilot receipt ending in `mmuxs`, 26,000 appears on both the subtotal and final-payment lines. The pilot rule returned the right value from the subtotal. On `cgbau`, the published annotation encloses the pre-discount 85,000 while the explicitly payable row shows 75,000. We preserved both published scores. A claims reviewer should see the field label alongside the amount. Numeric agreement alone cannot establish that the correct line supplied the evidence.

## Data, scoring, and scope

- The MC-OCR organizers describe mobile-phone collection and separate human annotation of field polygons and their text. We used the public training release as an external evaluation of this app. Image bytes and annotation revision are pinned in the runner. No photos or transcriptions are included in this repo's result files. [Original paper](https://people.cs.umu.se/sonvx/files/MCOCR_Preprint.pdf) · [Challenge specification](https://www.rivf2021-mc-ocr.vietnlp.com/dataset) · [Image mirror](https://github.com/huynhtinn/OCR/tree/84bde043360f840890b0aae8ed0a87318b647f4e/data) · [Annotation mirror](https://huggingface.co/datasets/tqhuyen/MC_OCR2021/tree/2eb1ead2be30d7194d38537f9bb5c4f48a8c8f06)
- We sorted all 1,155 image IDs by the SHA-256 of their filename and used positions 1–32 and 33–64. Each image has a distinct ID and byte digest. Merchants or templates can repeat. Of 128 possible field queries, 112 had a single parseable reference value. One pilot photo had no polygons; the other exclusions reflect missing, ambiguous, or unsupported value formats. No filtering by model output.
- The selector sees only OCR spans from the original page. Dates use a unique date candidate or a unique date on a date-labelled span. Totals use a recognized Vietnamese/English total label and a numeric value on the same line. Candidate and annotated crops go through identical local OCR, padding and normalization. Scoring uses day/month/two-digit year and normalized integer amounts. Full-page OCR also runs to propose the candidate, so the crop sizes do not establish compute savings.
- Coverage measures the fraction of the human value polygon retained by the selected crop: covered ≥90%, partial ≥10% and <90%, missed <10%. Where the same value has several annotated occurrences, any one can satisfy coverage. Correct answer and correct location are scored separately. The exact answer score gives no credit for declines. The reference reader uses the first annotated occurrence.
- Receipt rules were frozen at `b0ca1a1` for the held-out run. The shipped pipeline tree was `4b0d8c71c985`; the Apple Vision helper was freshly compiled from that tree. No GPU or paid API calls. This tests printed receipt fields. Handwritten accident forms, checkbox selection on real accident photos, and the app's final full-page model answer remain unmeasured.

## Reproduce and inspect

On macOS with Swift, Pillow and the repo's evaluation dependencies:

```sh
python3 -m bench.phone_receipts /tmp/mcocr --fetch --out pilot.jsonl --views /tmp/receipt-review
python3 -m bench.phone_receipts /tmp/mcocr --fetch --holdout --out holdout.jsonl --views /tmp/receipt-review
python3 -m bench.phone_receipt_review /tmp/receipt-review pilot.jsonl holdout.jsonl
```

Open `/tmp/receipt-review/index.html` locally. Select **total** and **Right value, missed region** to see eight pilot-rule examples across both cohorts. Green outlines show the reference and magenta outlines show the proposal. No web service is needed for review. [Pilot results](pilot.jsonl) · [Second cohort](holdout.jsonl)
