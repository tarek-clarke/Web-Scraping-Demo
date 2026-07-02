#!/bin/bash
#SBATCH --job-name=live-gpu-decoder
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --time=02:00:00
#SBATCH --signal=B:TERM@120
#SBATCH --output=live_decoder_%j.out
#SBATCH --error=live_decoder_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Live GPU Decoder Started ==="
echo "Node: $SLURM_NODENAME"
echo "Allocated GPUs: $SLURM_GPUS_ON_NODE"
echo "Start time: $(date)"

# Load modules
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate venv (absolute path)
source "$PROJECT_ROOT/.venv-lumi/bin/activate"

# Environment variables
export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache
export CHAOS_DEVICE=cuda:0

# Check GPU status
rocm-smi

# Check if sentence-transformers is installed in the environment
python3 -u -c "import sentence_transformers; print('sentence-transformers version:', sentence_transformers.__version__)"

# Kill the Go ingestor when this decoder job finishes
cleanup() {
    echo "[$(date)] Decoder finished. Killing ingestor..."
    kill $(cat "$PROJECT_ROOT/f1_ingestor.pid" 2>/dev/null) 2>/dev/null
    rm -f "$PROJECT_ROOT/f1_ingestor.pid"
}
trap cleanup EXIT

# Run live decoder polling telemetry_latest.json
python3 -u live_gpu_decoder.py --reconciler bert --chaos-rate 0.01 --poll-interval 1.0 --shadow-routing
