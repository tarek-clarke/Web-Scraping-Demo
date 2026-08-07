#!/bin/bash
#SBATCH --job-name=10indiv_gpus
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=02:00:00
#SBATCH --array=1-10
#SBATCH --output=logs/10indiv_gpu_%A_%a.out
#SBATCH --error=logs/10indiv_gpu_%A_%a.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-framework"
cd "$PROJECT_ROOT" || exit 1

RUN_NUM=$SLURM_ARRAY_TASK_ID
SUFFIX="_indiv_gpu_run$(printf '%02d' $RUN_NUM)"

echo "=========================================================================="
echo "=== Single GPU Benchmark Sweep (Task ${RUN_NUM}/10 - 1 Individual GPU) ==="
echo "=========================================================================="
echo "Job Array Task ID: $SLURM_ARRAY_TASK_ID"
echo "Host Node: $SLURM_NODENAME"
echo "Allocated GPU: 1x AMD Instinct MI250X GPU Device (64 GB VRAM)"
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

mkdir -p logs

echo "=== Launching 22,500-packet sweep on 1 individual GPU for Repetition ${RUN_NUM}/10 (${SUFFIX}) ==="
python3 run_matrix.py \
  --max-packets-per-api 2500 \
  --chaos-rate 0.10 \
  --repetitions 1 \
  --phases fast,bert,gemma \
  --run-number $RUN_NUM \
  --suffix "${SUFFIX}" \
  --packets-file data/ingested/telemetry_clean_bench_22500.json

echo "=========================================================================="
echo "=== Completed Repetition ${RUN_NUM}/10 on 1 Individual GPU ==="
echo "End time: $(date)"
echo "=========================================================================="
