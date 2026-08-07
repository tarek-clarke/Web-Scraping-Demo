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
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.11.7

# Activate venv
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
elif [ -f "$PROJECT_ROOT/.venv-lumi/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv-lumi/bin/activate"
elif [ -f "/scratch/project_465002996/clarketa/vlq-env/bin/activate" ]; then
    source "/scratch/project_465002996/clarketa/vlq-env/bin/activate"
else
    echo "ERROR: No compatible virtual environment found"
    exit 1
fi

# Export environment vars
export IS_LUMI=1

EXPECTED_GCDS=2
[ "${LUMI_GPU_PROFILE:-single}" = "full-node" ] && EXPECTED_GCDS=8
if [ "${SLURM_GPUS_ON_NODE:-}" != "$EXPECTED_GCDS" ]; then
    echo "ERROR: expected $EXPECTED_GCDS LUMI GCDs for profile ${LUMI_GPU_PROFILE:-single}, got '${SLURM_GPUS_ON_NODE:-unset}'" >&2
    exit 1
fi
python3 - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("ERROR: GPU training requested but torch.cuda.is_available() is false")
print(f"LUMI accelerator preflight: {torch.cuda.device_count()} visible device(s)")
PY

# Train one independent start per GPU.  The array therefore uses up to ten
# GPUs concurrently without sharing optimizer state between starts.
python3 -u scripts/train_qpu_router.py train \
    --oracle "${ORACLE:-data/training/router_oracle_22500_v4_${LUMI_GPU_PROFILE//-/_}.jsonl}" \
    --output-dir "data/training/qpu_router_multistart_v4_${LUMI_GPU_PROFILE//-/_}" \
    --start-index "$SLURM_ARRAY_TASK_ID" \
    --backend aer_gpu \
    --training-shots 512 \
    --maxiter 200

echo "=== Training Start ${SLURM_ARRAY_TASK_ID} Complete ==="
echo "End time: $(date)"
