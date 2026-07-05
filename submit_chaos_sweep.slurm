#!/bin/bash
#SBATCH --job-name=chaos-sweep
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=01:00:00
#SBATCH --output=sweep_%j.out
#SBATCH --error=sweep_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Starting Full GPU Chaos Sweep on Compute Node ==="
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
export CHAOS_DEVICE=cuda:0

# Run sweep on specified telemetry dataset (defaults to Qualifying)
export PYTHONPATH=.
python3 scripts/run_chaos_sweep.py "${1:-data/ingested/telemetry_20260704_170011.json}" "${2:-5}"

echo "=== Sweep Completed ==="
echo "End time: $(date)"
