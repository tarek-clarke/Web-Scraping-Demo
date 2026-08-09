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
if [ -z "${RAP_LUMI_PYTHON:-}" ]; then
    export PYTHONPATH="$LUMI_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
    export SINGULARITYENV_PYTHONPATH="$PYTHONPATH"
else
    unset PYTHONPATH SINGULARITYENV_PYTHONPATH
fi

module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings

LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
if [ ! -r "$LUMI_SIF" ]; then
    echo "ERROR: LUMI ROCm container not readable: $LUMI_SIF" >&2
    exit 1
fi
export LUMI_SIF
PYTHON_BIN=(singularity exec "$LUMI_SIF")
if [ -n "${RAP_LUMI_PYTHON:-}" ]; then
    PYTHON_BIN+=("$RAP_LUMI_PYTHON")
else
    PYTHON_BIN+=(python)
fi

export HF_TORCH_DTYPE=bfloat16
export TOKENIZERS_PARALLELISM=false

EXPECTED_GCDS=2
[ "${LUMI_GPU_PROFILE:-single}" = "full-node" ] && EXPECTED_GCDS=8
if [ "${SLURM_GPUS_ON_NODE:-}" != "$EXPECTED_GCDS" ]; then
    echo "ERROR: expected $EXPECTED_GCDS LUMI GCDs for profile ${LUMI_GPU_PROFILE:-single}, got '${SLURM_GPUS_ON_NODE:-unset}'" >&2
    exit 1
fi
if [ "${SLURM_NTASKS:-}" != "$EXPECTED_GCDS" ]; then
    echo "ERROR: expected $EXPECTED_GCDS one-GCD workers, got '${SLURM_NTASKS:-unset}'" >&2
    exit 1
fi
"${PYTHON_BIN[@]}" - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("ERROR: GPU oracle requested but torch.cuda.is_available() is false")
print(f"LUMI accelerator preflight: {torch.cuda.device_count()} visible device(s)")
PY

ORACLE="${ORACLE:-data/training/router_oracle_22500_v7_10pct_${LUMI_GPU_PROFILE//-/_}.jsonl}"
ORACLE_STEM="${ORACLE%.jsonl}"
SHARDS=()
for ((rank=0; rank<EXPECTED_GCDS; rank++)); do
    SHARDS+=("${ORACLE_STEM}.part_${rank}.jsonl")
done

export PROJECT_ROOT ORACLE RAP_LUMI_PYTHON
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
# Slurm already assigns one GCD per task through --gpus-per-task.  Do not
# impose a map_gpu list: LUMI allocation IDs are not task-local ordinals and
# can otherwise bind multiple workers to the first visible device.
echo "Launching $EXPECTED_GCDS scheduler-bound workers (two 64-GB GCD workers per 128-GB MI250X card)"
srun \
    --ntasks="$EXPECTED_GCDS" \
    --gpus-per-task=1 \
    --kill-on-bad-exit=1 \
    bash "$PROJECT_ROOT/scripts/slurm/run_router_oracle_shard.sh"

"${PYTHON_BIN[@]}" scripts/merge_router_oracle_shards.py \
    --output "$ORACLE" \
    --expected-records 2250 \
    --shards "${SHARDS[@]}"
