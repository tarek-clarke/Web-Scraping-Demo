#!/bin/bash
#SBATCH --job-name=oracle_train
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=01:00:00
#SBATCH --output=logs/oracle_train_%j.out
#SBATCH --error=logs/oracle_train_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-framework"
cd "$PROJECT_ROOT" || exit 1

echo "=========================================================================="
echo "=== VQC Quantum Router Oracle Pre-Calibration & Training (LUMI-G) ==="
echo "=========================================================================="
echo "Node: $SLURM_NODENAME"
echo "Allocated GPUs: $SLURM_GPUS_ON_NODE"
echo "Start time: $(date)"

# Load LUMI ROCm & Python environment
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate venv
source "$PROJECT_ROOT/.venv-lumi/bin/activate"

# Environment configuration
export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache
export TRANSFORMERS_OFFLINE=1

mkdir -p logs data/training

python3 scripts/build_router_oracle.py \
  --packets-file data/ingested/telemetry_clean_bench_22500.json \
  --seed 42

echo "=========================================================================="
echo "=== VQC Router Oracle Training Completed ==="
echo "End time: $(date)"
echo "=========================================================================="
