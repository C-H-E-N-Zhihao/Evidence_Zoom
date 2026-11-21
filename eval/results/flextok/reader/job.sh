#!/usr/bin/env bash
# FlexTok direct-code reader (Andrew dispatch andrew-flextok-reader.md). One A100, hard 14-min timeout.
set -uo pipefail
export HF_HOME=/mnt/scratch/zhichen/lauzhack/hf_cache HF_HUB_OFFLINE=1 TORCHDYNAMO_DISABLE=1
cd /mnt/scratch/zhichen/lauzhack/flextok/repo
OUT=/mnt/scratch/zhichen/lauzhack/flextok/reader; mkdir -p $OUT
T0=$(date +%s)
echo "== repo revision: d92fb3a (experiments/flextok_reader.py sha256 $(sha256sum experiments/flextok_reader.py | cut -c1-16))"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
pip install -q "https://github.com/apple/ml-flextok/archive/742f53d7135391069a94d65b897705fa1252c97c.zip" "diffusers==0.32.2" 2>&1 | tail -3
timeout 13m python -m experiments.flextok_reader --codes --save-ids $OUT/reader_ids.npz 2>&1 | tee $OUT/stdout.jsonl
echo "== exit ${PIPESTATUS[0]}  elapsed $(( $(date +%s) - T0 )) s" | tee -a $OUT/stdout.jsonl
