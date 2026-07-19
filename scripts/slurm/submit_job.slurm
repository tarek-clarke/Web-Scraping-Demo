#!/bin/bash
#SBATCH --job-name=resilient-rap
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=2
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=14
#SBATCH --mem=120G
#SBATCH --time=02:30:00
#SBATCH --output=job_%j.out
#SBATCH --error=job_%j.err

echo "=== Job Started ==="
echo "Node: $SLURM_NODENAME"
echo "Allocated GPUs: $SLURM_GPUS_ON_NODE"
echo "Start time: $(date)"

# Load modules
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate venv
source .venv-lumi/bin/activate

# Environment variables
export HF_TOKEN=${HF_TOKEN}
export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache
export CHAOS_DEVICE=cuda:1

# Check GPUs
rocm-smi

# Run script
python3 run_matrix.py --max-packets-per-api 500 --chaos-rate 0.05 --repetitions 1

echo "=== Job Finished ==="
echo "End time: $(date)"
