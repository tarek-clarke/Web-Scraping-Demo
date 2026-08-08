#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
source "$PROJECT_ROOT/scripts/lumi_cache_env.sh"

module purge
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.11.7
module load lumi-CrayPath

TRAIN_ENV="${RAP_LUMI_TRAIN_ENV:-$PROJECT_ROOT/.venv-aer-lumi}"
if [ ! -x "$TRAIN_ENV/bin/python3" ]; then
    python3 -m venv "$TRAIN_ENV"
fi
source "$TRAIN_ENV/bin/activate"
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements-router-training.txt
python3 -m pip check

echo "LUMI Aer Python environment ready: $TRAIN_ENV"
echo "Build and validate the ROCm Aer extension on a compute node with:"
echo "RAP_LUMI_TRAIN_ENV=$TRAIN_ENV sbatch --export=ALL,PROJECT_DIR=$PROJECT_ROOT,RAP_LUMI_TRAIN_ENV=$TRAIN_ENV scripts/slurm/rebuild_aer_rocm_tkde.slurm"
