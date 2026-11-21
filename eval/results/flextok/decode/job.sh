#!/usr/bin/env bash
# FlexTok decode diagnostic (message 115). One GPU, hard 28-min total timeout.
set -uo pipefail
export HF_HOME=/mnt/scratch/zhichen/lauzhack/hf_cache
export TORCHDYNAMO_DISABLE=1
cd /mnt/scratch/zhichen/lauzhack/flextok/repo
OUT=/mnt/scratch/zhichen/lauzhack/flextok/decode; mkdir -p $OUT
T0=$(date +%s); END=$((T0 + 28*60))
left() { echo $(( END - $(date +%s) )); }
echo "== repo revision: b5c8ee7 (experiments/flextok_marks.py with --save-dir)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
SHA=742f53d7135391069a94d65b897705fa1252c97c
pip install -q "https://github.com/apple/ml-flextok/archive/${SHA}.zip" "diffusers==0.32.2" 2>&1 | tail -3
for m in EPFL-VILAB/flextok_d12_d12_in1k EPFL-VILAB/flextok_d18_d28_dfn; do
  python -c "from huggingface_hub import model_info; print('== checkpoint revision:', '$m', model_info('$m').sha)"
done
M=EPFL-VILAB/flextok_d12_d12_in1k
for s in 1 2; do
  timeout $(left) python -m experiments.flextok_marks --codes-only --model $M --prefix 1 4 8 16 32 64 128 256 --seed $s | tee -a $OUT/codes_only_seeds12.jsonl
done
for s in 0 1 2; do
  echo "== decode $M seed $s  (left $(left) s)"
  timeout $(left) python -m experiments.flextok_marks --flextok --model $M --prefix 8 32 128 256 --seed $s --save-dir $OUT/strips | tee -a $OUT/decode_d12.jsonl
done
M=EPFL-VILAB/flextok_d18_d28_dfn
echo "== decode $M seed 0  (left $(left) s)"
timeout $(left) python -m experiments.flextok_marks --flextok --model $M --prefix 8 32 128 256 --seed 0 --save-dir $OUT/strips | tee -a $OUT/decode_d18d28.jsonl
echo "== done elapsed $(( $(date +%s) - T0 )) s"
