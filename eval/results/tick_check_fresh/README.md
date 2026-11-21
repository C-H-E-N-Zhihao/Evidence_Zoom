# Pixel tick check (`pipeline.anchor.tick_check`) on freshly generated forms: independent check by claude-zhihao

Code: master 792d8e3 (`tick_check` as added in 69e8d1c, `TICK_CHECK_MIN_PX = 1500`). $0, no model calls; Apple Vision OCR helper
compiled from `pipeline/ocr/recognize.swift`. Pillow 13.0.0.

**Fresh data, never seen when the threshold was set:** 6 pairs per layout, **seed 90210**, written to a scratch folder (not
committed; regenerate with the commands below). Layout 1 = `accident_statement` generator v1, layout 2 = `--layout v2`, layout 3 =
`accident_statement_v3` generator with `EAS3_SEED=90210`. 24 tick questions per layout (B's ticked boxes + "did A tick 8").

## Clean, full resolution (1700 × 2200 or A4 equivalent)

| set | correct | wrong | unavailable |
|---|---:|---:|---:|
| fresh layout 1 | 24 | 0 | 0 |
| fresh layout 2 | 24 | 0 | 0 |
| fresh layout 3 | 24 | 0 | 0 |
| committed layout 1 (dev) | 24 | 0 | 0 |
| committed layout 3 (dev, canonical images) | 24 | 0 | 0 |

**72/72 on unseen forms**, which reproduces 142's development result on new seeds.

## Full-resolution degradations (the 1500 px gate does **not** stop these)

| condition (from `bench.ocr_robustness`) | fresh layout 1: correct / wrong / unavailable | fresh layout 3 |
|---|---|---|
| jpeg_q40 | 24 / 0 / 0 | 24 / 0 / 0 |
| perspective_3% | 24 / 0 / 0 | 0 / 0 / 24 (declined) |
| rotate_5 | **22 / 2 / 0** | 0 / 0 / 24 (declined) |
| blur_1.5 | **10 / 14 / 0** | 24 / 0 / 0 |
| photo_fullres (phone_photo without the 1280 px downscale: 2.5° + 3 % perspective + blur 1.2 + JPEG 55) | **12 / 12 / 0** | 0 / 0 / 24 (declined) |
| scale_1280 | 0 / 0 / 24 (gated) | 0 / 0 / 24 (gated) |

**Reading.** On clean or JPEG full-resolution scans the check is reliable, also on new forms. But the resolution gate is not
a quality gate: a **blurred or photographed page that keeps ≥ 1500 px passes the gate and the check is then wrong in up to
14/24 cases on layout 1**, in a way that shows up in the app as a confident "agrees" or "disagrees". Layout 3 declines most distorted
pages instead (the template layout isn't found), which is the safe failure. Also: 5° tilt gave 2 wrong on fresh layout 1, where 142
reported 24/24 on the development forms.

Reproduce (from the repo root, `SP` = any scratch folder, `EVIDENCE_OCR_BIN` = the compiled helper):

```sh
python -m eval.data.accident_statement.generate --n 6 --seed 90210 --layout v1 --out-dir $SP/tickcheck_v1
python -m eval.data.accident_statement.generate --n 6 --seed 90210 --layout v2 --out-dir $SP/tickcheck_v2
EAS3_SEED=90210 EAS3_OUT=$SP/tickcheck_v3 EAS3_PREFIX=tc3 python -m eval.data.accident_statement_v3.generate
PYTHONPATH=. python eval/results/tick_check_fresh/score_tickcheck.py $SP/tickcheck_v1 $SP/tickcheck_v2 $SP/tickcheck_v3
PYTHONPATH=. python eval/results/tick_check_fresh/tickcheck_degr.py $SP/tickcheck_v1 $SP/tickcheck_v3
```

Caveat: the v3 generator **ignores `--help`** and writes into its own folder by default. Running it without `EAS3_OUT` overwrites
the local (git-ignored) v3 images with Pillow-13 renders that no longer match `images.sha256`. Restore them from
`origin/data/blind-family-images`.

## Re-run by claude-andrew-b after the quality gates (message 144)

Same fresh seed-90210 forms and scripts, `pipeline.anchor.tick_check` with three gates added: sharpness (variance of the
Laplacian over the tick column ≥ 1,500, threshold set on development layout 1 only: clean/JPEG/tilt/perspective ≥ 4,000,
blur and full-resolution photo 150–350), box outline found on ≥ 90 % of rows, and straightening ≤ 3°.

| condition | fresh layout 1: correct / wrong / unavailable | fresh layout 3 |
|---|---|---|
| clean (layouts 1, 2, 3) | 24/0/0 each (72/72) | |
| jpeg_q40 | 24 / 0 / 0 | 24 / 0 / 0 |
| perspective_3% | 24 / 0 / 0 | 0 / 0 / 24 |
| rotate_5 | 0 / 0 / 24 (declined by the tilt gate) | 0 / 0 / 24 |
| blur_1.5 | **0 / 0 / 24** (was 10 / 14 / 0) | 0 / 0 / 24 |
| photo_fullres | **0 / 0 / 24** (was 12 / 12 / 0) | 0 / 0 / 24 |
| scale_1280 | 0 / 0 / 24 | 0 / 0 / 24 |

The sharpness gate was calibrated on development forms and then run once on these fresh forms (validated). **The ≤ 3° tilt
gate was added after seeing the 2 wrong answers at 5° here**, so it is conservative but not validated by this data.

## Re-test after the quality gates (3b45dbf, message 144), by claude-zhihao

Same scripts at master 09038d1. Seed 90210 (the gates were run on it once) **and a new seed 31337** (unseen by anyone; same three generators,
`EAS3_SEED=31337 EAS3_PREFIX=tc3b` for layout 3). This time the degradations were also run on **layout 2**.

| set | clean | jpeg_q40 | blur_1.5 | rotate_5 | photo_fullres | scale_1280 | perspective_3% |
|---|---|---|---|---|---|---|---|
| 90210 layout 1 | 24/0/0 | 24/0/0 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 24/0/0 |
| 90210 layout 2 | 24/0/0 | – | – | 0/0/24 | – | – | **12/12/0** |
| 90210 layout 3 | 24/0/0 | 24/0/0 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |
| 31337 layout 1 | 24/0/0 | 24/0/0 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 24/0/0 |
| 31337 layout 2 | 24/0/0 | 24/0/0 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | **12/12/0** |
| 31337 layout 3 | 24/0/0 | 24/0/0 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 | 0/0/24 |

(correct / wrong / declined, of 24.) The gates fixed blur, the full-resolution photo and 5° tilt: all now decline. **One hole remains: layout 2 under
3 % perspective, 12/24 wrong on both seeds.** It's always a phantom tick on **row 13** (e.g. gold "none" → check "13"; gold "8" →
"8, 11, 13"), while the yes/no row-8 questions stay right. Perspective isn't caught by the tilt (rotation) gate, and the bottom rows'
cells drift. Clean-scan accuracy after the gates: **72/72 on the unseen seed 31337** (3 sets × 24). Seed 90210 also scores 72/72, but it had already informed the tilt gate (144), so it doesn't count as unseen (release review andrew-pixel-review).

## Re-test after the perspective fix (0dc0f37, message 146), by claude-zhihao

Code at master b666957. **New seed 777000**, generated after the fix and never seen by anyone (`EAS3_PREFIX=tc3c` for layout 3); seed 31337
for comparison (it was used during the fix, per 146's disclosure, so it no longer counts as unseen).

| set | clean | perspective_3% | jpeg_q40 | blur_1.5 · rotate_5 · photo_fullres · scale_1280 |
|---|---|---|---|---|
| 777000 layout 1 | 24/0/0 | 24/0/0 | 24/0/0 | all declined |
| **777000 layout 2** | 24/0/0 | **24/0/0** (was 12/12) | 24/0/0 | all declined |
| 777000 layout 3 | 24/0/0 | declined | 24/0/0 | all declined |
| 31337 layouts 1–3 | 72/0/0 | 24/0/0 (l1), 24/0/0 (l2), declined (l3) | 72/0/0 | all declined |

**On the unseen seed 777000: clean 72/72, and 0 wrong in every tested condition.** The layout-2 phantom row 13 is gone. Every other
distortion still declines, which is the safe failure. The scope stays as approved: clean full-resolution scans of configured synthetic layouts;
real phone photos are untested.
