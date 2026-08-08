#!/bin/bash
#SBATCH --job-name=vqc-train
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --array=0-9
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=12:00:00
#SBATCH --output=vqc_train_%A_%a.out
#SBATCH --error=vqc_train_%A_%a.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$PROJECT_ROOT" || exit 1

echo "=== Starting VQC Router Training on Compute Node ==="
echo "Node: ${SLURM_NODENAME:-${SLURMD_NODENAME:-unknown}}"
echo "Start time: $(date)"

# Load modules
module purge
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.11.7
if module is-loaded PrgEnv-cray >/dev/null 2>&1; then
    module swap PrgEnv-cray PrgEnv-gnu
else
    module load PrgEnv-gnu
fi
module load lumi-CrayPath

# Keep the ROCm/Aer environment separate from the Python 3.12 inference
# container. Compiled extensions from the container runtime layer are not ABI
# compatible with this Python 3.11 environment.
TRAIN_ENV="${RAP_LUMI_TRAIN_ENV:-$PROJECT_ROOT/.venv-aer-lumi}"
if [ ! -f "$TRAIN_ENV/bin/activate" ]; then
    echo "ERROR: missing isolated LUMI Aer environment: $TRAIN_ENV" >&2
    echo "Run bash scripts/bootstrap_lumi_aer_env.sh first." >&2
    exit 1
fi
source "$TRAIN_ENV/bin/activate"
echo "Training environment: $TRAIN_ENV"
python3 -m pip check

# Export environment vars
export IS_LUMI=1
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export RAP_REQUIRE_GPU_TELEMETRY=1
if [[ ! "${SLURM_JOB_GPUS:-}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: expected one scheduler-assigned GCD ID, got '${SLURM_JOB_GPUS:-unset}'" >&2
    exit 1
fi
export RAP_ASSIGNED_GPU_ID="$SLURM_JOB_GPUS"

EXPECTED_GCDS=1
if [ "${SLURM_GPUS_ON_NODE:-}" != "$EXPECTED_GCDS" ]; then
    echo "ERROR: each independent optimizer start requires exactly one LUMI GCD; got '${SLURM_GPUS_ON_NODE:-unset}'" >&2
    exit 1
fi
python3 scripts/preflight_accelerator.py \
    --expected-devices "$EXPECTED_GCDS" \
    --profile training \
    --accelerator-runtime aer \
    --require-aer \
    --require-router-qnn \
    --json-output "data/training/preflight_train_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.json"

if [ "${RAP_PREFLIGHT_ONLY:-0}" = "1" ]; then
    echo "Training environment preflight complete; optimization was not started."
    exit 0
fi

# Train one independent start per GCD. The array can therefore use up to ten
# GCDs concurrently without pretending a small 14-qubit statevector scales
# efficiently across an entire multi-GPU node.
python3 scripts/run_with_energy.py \
    --csv "data/training/energy_train_${LUMI_GPU_PROFILE//-/_}_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.csv" \
    --summary "data/training/energy_train_${LUMI_GPU_PROFILE//-/_}_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.json" \
    --label "lumi-vqc-train-${LUMI_GPU_PROFILE}-${SLURM_ARRAY_TASK_ID}" -- \
    python3 -u scripts/train_qpu_router.py train \
        --oracle "${ORACLE:-data/training/router_oracle_22500_v4_${LUMI_GPU_PROFILE//-/_}.jsonl}" \
        --output-dir "data/training/qpu_router_multistart_v4_${LUMI_GPU_PROFILE//-/_}" \
        --start-index "$SLURM_ARRAY_TASK_ID" \
        --backend aer_gpu \
        --training-shots 512 \
        --maxiter 200

echo "=== Training Start ${SLURM_ARRAY_TASK_ID} Complete ==="
echo "End time: $(date)"
