#!/bin/bash
set -euo pipefail

: "${PROJECT_ROOT:?PROJECT_ROOT is required}"
: "${LUMI_SIF:?LUMI_SIF is required}"
: "${SLURM_PROCID:?This probe must run under srun}"
cd "$PROJECT_ROOT"
exec >"rap_gpu_bind_${SLURM_JOB_ID}_part_${SLURM_PROCID}.out" \
     2>"rap_gpu_bind_${SLURM_JOB_ID}_part_${SLURM_PROCID}.err"

env | sort | sed -n '/GPU/p;/VISIBLE_DEVICES/p'

singularity run "$LUMI_SIF" python scripts/preflight_accelerator.py \
    --expected-devices 1 \
    --profile oracle \
    --json-output "data/training/preflight_binding_${SLURM_JOB_ID}_${SLURM_PROCID}.json"
