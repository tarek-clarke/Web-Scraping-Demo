#!/bin/bash
#SBATCH --job-name=rap-framework
#SBATCH --output=rap-%j.out
#SBATCH --error=rap-%j.err
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --gpus-per-node=1
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --account=project_465000880

# LUMI HPC Slurm Job Script for Resilient RAP Framework
# Submit with: sbatch slurm-lumi.sh

set -e  # Exit on error

echo "=== LUMI HPC Job Started ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "GPUs: $SLURM_GPUS_ON_NODE"
echo "Start time: $(date)"
echo ""

# Load modules
echo "Loading modules..."
module load LUMI/23.09
module load partition/G
module load lumi-multitorch/2.1.0-rocm5.6.1-python3.11.7

echo "✓ Modules loaded"

# Activate virtual environment
if [ -d ".venv-lumi" ]; then
    echo "Activating virtual environment..."
    source .venv-lumi/bin/activate
    echo "✓ Virtual environment activated"
else
    echo "ERROR: Virtual environment not found. Run setup-lumi.sh first."
    exit 1
fi

# Set environment variables for LUMI
export IS_LUMI=1
export HF_MODEL_ID=${HF_MODEL_ID:-"google/gemma-4-E2B-it"}
export CHAOS_MODEL_ID=${CHAOS_MODEL_ID:-"Qwen/Qwen2.5-7B-Instruct"}
export USE_LLM_CHAOS=${USE_LLM_CHAOS:-"true"}

# Optional: Set HF_TOKEN if not already set
if [ -z "$HF_TOKEN" ]; then
    echo "WARNING: HF_TOKEN not set. Some models may not be accessible."
fi

echo ""
echo "Environment:"
echo "  IS_LUMI: $IS_LUMI"
echo "  HF_MODEL_ID: $HF_MODEL_ID"
echo "  CHAOS_MODEL_ID: $CHAOS_MODEL_ID"
echo "  USE_LLM_CHAOS: $USE_LLM_CHAOS"
echo ""

# Check GPU availability
echo "GPU Information:"
rocm-smi --showproductname || echo "rocm-smi not available"
echo ""

# Run the framework
echo "Starting Resilient RAP Framework..."
echo ""

python3 run_matrix.py \
    --max-packets-per-api 500 \
    --chaos-rate 0.05 \
    --repetitions 1

echo ""
echo "=== Job Completed ==="
echo "End time: $(date)"
echo ""
echo "Results saved to: data/reports/"
