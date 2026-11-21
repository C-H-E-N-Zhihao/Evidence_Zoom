# FlexTok encode-only prefix probe (Andrew dispatch 645d00c), run by claude-zhihao on RCP

Command (from `experiments/FLEXTOK.md`): `python -m experiments.flextok_marks --codes-only --model EPFL-VILAB/flextok_d12_d12_in1k --prefix 1 4 8 16 32 64 128 256`
Output: [`flextok_codes_only.jsonl`](flextok_codes_only.jsonl) (stdout lines). Job script: [`job.sh`](job.sh).

| provenance | value |
|---|---|
| LauzHack repo | 3db675e (`experiments/flextok_marks.py` sha256 67cb7390…, `eas-001a.png` sha256 03f06ab7…) |
| ml-flextok | commit 742f53d7135391069a94d65b897705fa1252c97c, with `diffusers==0.32.2` (newest diffusers needs torch ≥ 2.6) |
| checkpoint | EPFL-VILAB/flextok_d12_d12_in1k @ fe24b9794f32cc5c002781d25dd81a7768bed71c |
| hardware | 1 × NVIDIA A100-SXM4-40GB, preemptible train job, image pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime |
| mode | float32, **eager** (`TORCHDYNAMO_DISABLE=1`: the runtime image has no C compiler for torch.compile), timings are uncompiled first-use |
| job | `lh-flextok-probe3`, script elapsed 34 s; 2 earlier attempts failed at setup in < 1 min each (diffusers/torch mismatch, then torch.compile). Total ≈ 0.1 GPU-h |

## Result (5 cases: blank + one tick moved through 4 rows; one form, one seed)

`max_correct_on_cases` = the most of the 5 cases any deterministic reader of that prefix could classify correctly
(cases with identical prefixes are indistinguishable).

| prefix | whole page (256×256 pad) | known crop (256×256) |
|---:|---|---|
| 1 | 1/5 (blank collides with all 4 ticks) | **5/5** |
| 4 | 1/5 (blank collides with all 4) | 5/5 |
| 8 | 2/5 (blank collides with row 1) | 5/5 |
| 16–256 | **5/5** | 5/5 |

Load 6.8 s; encode 0.72 s per 5 whole-page inputs and 0.19 s per 5 crops (first use, includes warm-up); peak
allocated 1.56 GB, reserved 1.68 GB. CPU resize controls (same run): whole page recovers 4/4 at ≥ 128 px and 0/4 at
≤ 64 px; the crop recovers 4/4 down to 16 px.

## Reading (per the decision table in FLEXTOK.md)

- On the whole page, short prefixes (≤ 8 codes) **cannot** tell the five cases apart; from 16 codes the IDs are
  distinct. With the known region, even 1 code separates them. That is FLEXTOK.md's "only the known region separates
  them early → pursue spatial indexing" branch.
- **Distinct IDs are a necessary condition, not readability**: whether a reader can decode the tick from those codes
  is untested (FLEXTOK.md step 3). n = 5 cases, one form, one seed, no warm-repeat timing yet.
