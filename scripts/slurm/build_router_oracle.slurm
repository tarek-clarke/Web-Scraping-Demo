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

export HF_TORCH_DTYPE=bfloat16
export TOKENIZERS_PARALLELISM=false

python3 -u scripts/build_router_oracle.py \
    --packets-file data/ingested/telemetry_clean_bench_22500.json \
    --output data/training/router_oracle_22500_v2.jsonl \
    --max-packets-per-api 2500 \
    --chunk-size 64 \
    --batch-size 64 \
    --accuracy-sla 0.95 \
    --resume
