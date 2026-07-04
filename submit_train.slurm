#!/bin/bash
#SBATCH --job-name=vqc-train
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=00:10:00
#SBATCH --output=vqc_train_%j.out
#SBATCH --error=vqc_train_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Starting VQC Router Training on Compute Node ==="
echo "Node: $SLURM_NODENAME"
echo "Start time: $(date)"

# Load modules
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate venv
source "$PROJECT_ROOT/.venv-lumi/bin/activate"

# Export environment vars
export IS_LUMI=1

# Run the training script
python3 scripts/train_router.py

echo "=== Training Job Complete ==="
echo "End time: $(date)"
