#!/bin/bash
#SBATCH --job-name=live-gpu-decoder
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --time=00:15:00
#SBATCH --output=live_decoder_%j.out
#SBATCH --error=live_decoder_%j.err

echo "=== Live GPU Decoder Started ==="
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
export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache
export CHAOS_DEVICE=cuda:0

# Check GPU status
rocm-smi

# Check if sentence-transformers is installed in the environment
python3 -c "import sentence_transformers; print('sentence-transformers version:', sentence_transformers.__version__)"

# Run live decoder polling telemetry_latest.json
python3 live_gpu_decoder.py --reconciler bert --chaos-rate 0.10 --poll-interval 5.0
