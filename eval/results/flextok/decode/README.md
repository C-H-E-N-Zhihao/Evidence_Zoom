# FlexTok decode diagnostic (FLEXTOK.md row 2), message 115/116, run by claude-zhihao on RCP

Command per seed s ∈ {0,1,2}: `python -m experiments.flextok_marks --flextok --model EPFL-VILAB/flextok_d12_d12_in1k --prefix 8 32 128 256 --seed $s --save-dir strips`
(20 flow steps, guidance 7.5, the runner's defaults). Codes-only was repeated for seeds 1 and 2. Script: [`job.sh`](job.sh).

| provenance | value |
|---|---|
| LauzHack repo | b5c8ee7 |
| ml-flextok | 742f53d7135391069a94d65b897705fa1252c97c, `diffusers==0.32.2`, torch 2.5.1+cu124, fp32, eager (`TORCHDYNAMO_DISABLE=1`) |
| checkpoint | EPFL-VILAB/flextok_d12_d12_in1k @ fe24b9794f32cc5c002781d25dd81a7768bed71c |
| hardware / job | 1 × A100-SXM4-40GB, `lh-flextok-decode`, 233 s elapsed, ≈ 0.07 GPU-h, deleted |
| d18-d28 arm | **not run**: the checkpoint download failed inside `huggingface_hub`/httpx (`TypeError: process() takes no keyword arguments`). This is an environment bug, not a model result ([`decode_d18d28.jsonl`](decode_d18d28.jsonl) holds only the resize controls) |

## Results (5 cases: blank + one tick moved through 4 rows; one form; 3 decoder seeds)

`moved` = moved rows read correctly (of 4) by the runner's fixed ink reader on the reconstruction; `blank` = no tick read on the blank control.

| prefix | page: moved | page: blank clean | crop: moved | crop: blank clean |
|---:|---|---|---|---|
| 8 | 0/4, 0/4, 0/4 | yes ×3 (nothing drawn) | 0/4 ×3 | no ×3 |
| 32 | 0/4 ×3 | 2 of 3 seeds | 0/4 ×3 | no ×3 |
| 128 | 0/4 ×3 | no ×3 | **4/4 ×3** | **yes ×3** |
| 256 | 0/4 ×3 | no ×3 | **4/4 ×3** | **yes ×3** |

Codes-only repeated with seeds 1 and 2: identical to seed 0 (page distinct from 16 codes, crop from 1).

**What the strips show** (`strips/*.png`, input on top, reconstruction below):
- **Whole page** (`…page_seed0_prefix256.png`): the 256×256 page reconstruction turns the text into glyph-like noise. The
  moved tick isn't kept at any prefix. "Ticks" on the blank at 128/256 are smeared ink that the reader flags, so the
  page arm fails **outright, not marginally**.
- **Known crop** (`…crop_seed0_prefix256.png`): a distorted but correct tick appears in the right row, with the
  blank clean. At 8/32 codes the decoder generates a different image (`…crop_seed0_prefix32.png`), with no boxes in the right place.

## Reading against the predictions committed in message 115

- Page at prefix 8 ≤ 2/4: **held** (0/4). The page also fails at every larger prefix, which the prediction didn't cover.
- Crop at 256 → 4/4 with the blank clean: **held** in 3/3 seeds, and also at 128.
- So the moved tick shows up in the reconstruction **only after the region has been selected** and given ≥ 128 of the 256
  codes. Global FlexTok at 256 px doesn't keep form content. This matches the CPU control (the page needs ≥ 128 px
  of resolution for the tick) and the project's design: **select the region first, at source resolution**.
- Scope: n = 5 inputs, one form, one checkpoint, reconstructions read by a fixed pixel reader. This doesn't test a
  direct-code reader (FLEXTOK.md step 3), and the timings are first-use and eager.
