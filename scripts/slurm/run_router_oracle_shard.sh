#!/bin/bash
set -euo pipefail

: "${PROJECT_ROOT:?PROJECT_ROOT is required}"
: "${ORACLE:?ORACLE is required}"
: "${ORACLE_SHARDS:?ORACLE_SHARDS is required}"
: "${LUMI_SIF:?LUMI_SIF is required}"
: "${SLURM_PROCID:?This launcher must run under srun}"
: "${SLURM_LOCALID:?This launcher must run under srun}"
: "${RAP_SLURM_GPU_MAP:?The allocation-derived GPU map is required}"

cd "$PROJECT_ROOT"
source "$PROJECT_ROOT/scripts/lumi_cache_env.sh"
RANK="$SLURM_PROCID"
SHARD="${ORACLE%.jsonl}.part_${RANK}.jsonl"
export RAP_CPU_WORKERS="${SLURM_CPUS_PER_TASK:-1}"
IFS=',' read -r -a ALLOCATED_GPU_IDS <<< "$RAP_SLURM_GPU_MAP"
if [ "${#ALLOCATED_GPU_IDS[@]}" -ne "$ORACLE_SHARDS" ] || [ -z "${ALLOCATED_GPU_IDS[$SLURM_LOCALID]:-}" ]; then
    echo "ERROR: cannot resolve physical GCD for local rank ${SLURM_LOCALID:-unset}" >&2
    exit 1
fi
export RAP_ASSIGNED_GPU_ID="${ALLOCATED_GPU_IDS[$SLURM_LOCALID]}"
export RAP_REQUIRE_GPU_TELEMETRY=1
export IS_LUMI=1
if (( RAP_ASSIGNED_GPU_ID % 2 == 0 )); then
    export RAP_ENERGY_SENSOR_OWNER=1
else
    export RAP_ENERGY_SENSOR_OWNER=0
fi
export SINGULARITYENV_RAP_ASSIGNED_GPU_ID="$RAP_ASSIGNED_GPU_ID"
export SINGULARITYENV_RAP_REQUIRE_GPU_TELEMETRY=1
export SINGULARITYENV_RAP_ENERGY_SENSOR_OWNER="$RAP_ENERGY_SENSOR_OWNER"
export SINGULARITYENV_IS_LUMI=1
exec >"router_oracle_${SLURM_JOB_ID}_part_${RANK}.out" \
     2>"router_oracle_${SLURM_JOB_ID}_part_${RANK}.err"

env | sort | sed -n '/GPU/p;/VISIBLE_DEVICES/p'

# Slurm supplies the ROCm device namespace through --gpus-per-task and the
# allocation-derived map_gpu binding. Do not replace it with fixed indices:
# LUMI GCD identifiers are allocation-specific. The preflight records each
# task's physical PCI/UUID identity so duplicate assignments fail review.
singularity run "$LUMI_SIF" python scripts/preflight_accelerator.py \
    --expected-devices 1 \
    --profile oracle \
    --require-cohere \
    --json-output "${ORACLE%.jsonl}.part_${RANK}.preflight.json"

# Qwen generation is independently executed on each 64-GB GCD. Two workers
# share each physical 128-GB MI250X card and maximize aggregate throughput.
singularity run "$LUMI_SIF" python scripts/run_with_energy.py \
    --csv "${SHARD%.jsonl}.energy.csv" \
    --summary "${SHARD%.jsonl}.energy_summary.json" \
    --label "lumi-oracle-${LUMI_GPU_PROFILE:-unknown}-shard-${RANK}" -- \
    python -u scripts/build_router_oracle.py \
        --packets-file data/ingested/telemetry_clean_bench_22500.json \
        --output "$SHARD" \
        --max-packets-per-api 2500 \
        --chunk-size 31500 \
        --batch-size 4 \
        --accuracy-sla 0.95 \
        --num-shards "$ORACLE_SHARDS" \
        --shard-index "$RANK" \
        --resume
