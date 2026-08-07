#!/bin/bash
#SBATCH --job-name=vqc-select
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=02:00:00
#SBATCH --output=vqc_select_%j.out
#SBATCH --error=vqc_select_%j.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$PROJECT_ROOT"

module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.11.7

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

python3 -u scripts/train_qpu_router.py select \
    --oracle "${ORACLE:-data/training/router_oracle_22500_v4_${LUMI_GPU_PROFILE//-/_}.jsonl}" \
    --candidates-dir "data/training/qpu_router_multistart_v4_${LUMI_GPU_PROFILE//-/_}" \
    --model-output "configs/quantum_router_v4_${LUMI_GPU_PROFILE//-/_}.json" \
    --expected-starts 10 \
    --backend aer_gpu \
    --evaluation-shots 2048 \
    --min-macro-f1 0.70 \
    --min-balanced-accuracy 0.70
