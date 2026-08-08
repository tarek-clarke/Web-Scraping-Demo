#!/bin/bash
#SBATCH --job-name=router-oracle
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --time=36:00:00
#SBATCH --output=router_oracle_%j.out
#SBATCH --error=router_oracle_%j.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
cd "$PROJECT_ROOT"
source "$PROJECT_ROOT/scripts/lumi_cache_env.sh"

LUMI_SITE_PACKAGES="${RAP_LUMI_SITE_PACKAGES:-${PROJECT_ROOT}/.runtime/lumi/site-packages}"
if [ ! -d "$LUMI_SITE_PACKAGES" ]; then
    echo "ERROR: missing LUMI runtime layer; run bash scripts/bootstrap_lumi_runtime.sh" >&2
    exit 1
fi
export PYTHONPATH="$LUMI_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
export SINGULARITYENV_PYTHONPATH="$PYTHONPATH"

module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings

LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
if [ ! -r "$LUMI_SIF" ]; then
    echo "ERROR: LUMI ROCm container not readable: $LUMI_SIF" >&2
    exit 1
fi
export LUMI_SIF
PYTHON_BIN=(singularity run "$LUMI_SIF" python)

export HF_TORCH_DTYPE=bfloat16
export TOKENIZERS_PARALLELISM=false

EXPECTED_GCDS=2
[ "${LUMI_GPU_PROFILE:-single}" = "full-node" ] && EXPECTED_GCDS=8
if [ "${SLURM_GPUS_ON_NODE:-}" != "$EXPECTED_GCDS" ]; then
    echo "ERROR: expected $EXPECTED_GCDS LUMI GCDs for profile ${LUMI_GPU_PROFILE:-single}, got '${SLURM_GPUS_ON_NODE:-unset}'" >&2
    exit 1
fi
if [ "${SLURM_NTASKS:-}" != "$EXPECTED_GCDS" ]; then
    echo "ERROR: expected $EXPECTED_GCDS Slurm tasks, got '${SLURM_NTASKS:-unset}'" >&2
    exit 1
fi
"${PYTHON_BIN[@]}" - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("ERROR: GPU oracle requested but torch.cuda.is_available() is false")
print(f"LUMI accelerator preflight: {torch.cuda.device_count()} visible device(s)")
PY

ORACLE="${ORACLE:-data/training/router_oracle_22500_v4_${LUMI_GPU_PROFILE//-/_}.jsonl}"
ORACLE_STEM="${ORACLE%.jsonl}"
SHARDS=()
for ((rank=0; rank<EXPECTED_GCDS; rank++)); do
    SHARDS+=("${ORACLE_STEM}.part_${rank}.jsonl")
done

export PROJECT_ROOT ORACLE
export ORACLE_SHARDS="$EXPECTED_GCDS"
GPU_MAP="${SLURM_JOB_GPUS:-}"
if [[ ! "$GPU_MAP" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
    echo "ERROR: unsupported SLURM_JOB_GPUS value: '$GPU_MAP'" >&2
    exit 1
fi
IFS=',' read -r -a GPU_IDS <<< "$GPU_MAP"
if [ "${#GPU_IDS[@]}" -ne "$EXPECTED_GCDS" ]; then
    echo "ERROR: Slurm granted ${#GPU_IDS[@]} GPU IDs for $EXPECTED_GCDS workers" >&2
    exit 1
fi
export RAP_SLURM_GPU_MAP="$GPU_MAP"
# Slurm's GPU IDs are node-level allocation identifiers. On LUMI a
# one-card allocation can legitimately be reported as `0,2`, while the
# srun step exposes the allocated devices as task-local ordinals `0,1`.
# Bind by task-local ordinal and retain the allocation IDs separately for
# physical-device provenance and telemetry mapping.
LOCAL_GPU_MAP=""
for ((rank=0; rank<EXPECTED_GCDS; rank++)); do
    if [ -n "$LOCAL_GPU_MAP" ]; then
        LOCAL_GPU_MAP+=","
    fi
    LOCAL_GPU_MAP+="$rank"
done
echo "Launching $EXPECTED_GCDS scheduler-bound workers (one Slurm task per GCD)"
srun \
    --ntasks="$EXPECTED_GCDS" \
    --gpus-per-task=1 \
    --gpu-bind="map_gpu:$LOCAL_GPU_MAP" \
    --kill-on-bad-exit=1 \
    bash "$PROJECT_ROOT/scripts/slurm/run_router_oracle_shard.sh"

"${PYTHON_BIN[@]}" scripts/merge_router_oracle_shards.py \
    --output "$ORACLE" \
    --expected-records 31500 \
    --shards "${SHARDS[@]}"
