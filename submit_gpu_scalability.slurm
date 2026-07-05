#!/bin/bash
#SBATCH --job-name=gpu-scalability
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --time=00:30:00
#SBATCH --output=scalability_%j.out
#SBATCH --error=scalability_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Starting GPU Scalability Benchmark (1 to 8 GPUs) ==="
echo "Node: $SLURM_NODENAME"
echo "Allocated GPUs: $SLURM_GPUS_ON_NODE"
echo "Start time: $(date)"

# Load modules
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate venv
source "$PROJECT_ROOT/.venv-lumi/bin/activate"

# Environment variables
export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache

# Run GPU scalability sweep script
export PYTHONPATH=.
python3 scripts/run_gpu_scalability_sweep.py

echo "=== Benchmark Completed ==="
echo "End time: $(date)"
