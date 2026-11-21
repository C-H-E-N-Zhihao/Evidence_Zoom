#!/usr/bin/env bash
# FlexTok encode-only prefix probe (Andrew dispatch 645d00c). One GPU, hard 25-min timeout.
set -uo pipefail
export HF_HOME=/mnt/scratch/zhichen/lauzhack/hf_cache
export TORCHDYNAMO_DISABLE=1  # no C compiler in the runtime image: eager mode, timings are uncompiled
cd /mnt/scratch/zhichen/lauzhack/flextok/repo
T0=$(date +%s)
echo "== repo revision: 3db675e (experiments/flextok_marks.py + eas-001a.png copied; sha256 in job dir)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
SHA=742f53d7135391069a94d65b897705fa1252c97c
echo "== ml-flextok commit: $SHA"
pip install -q "https://github.com/apple/ml-flextok/archive/${SHA:-main}.zip" "diffusers==0.32.2" 2>&1 | tail -3
python -c "from huggingface_hub import model_info; print('== checkpoint revision:', model_info('EPFL-VILAB/flextok_d12_d12_in1k').sha)"
timeout 25m python -m experiments.flextok_marks --codes-only --model EPFL-VILAB/flextok_d12_d12_in1k --prefix 1 4 8 16 32 64 128 256 | tee ../flextok_codes_only.jsonl
echo "== exit ${PIPESTATUS[0]}  elapsed $(( $(date +%s) - T0 )) s"
