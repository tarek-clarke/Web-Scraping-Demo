#!/bin/bash
#SBATCH --job-name=1full_mi250x
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=2
#SBATCH --ntasks-per-node=2
#SBATCH --cpus-per-task=14
#SBATCH --time=02:00:00
#SBATCH --array=1-10
#SBATCH --output=logs/1full_mi250x_%A_%a.out
#SBATCH --error=logs/1full_mi250x_%A_%a.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-framework"
cd "$PROJECT_ROOT" || exit 1

RUN_NUM=$SLURM_ARRAY_TASK_ID
SUFFIX="_1full_mi250x_128gb_run$(printf '%02d' $RUN_NUM)"

echo "=========================================================================="
echo "=== 1 Full Physical MI250X GPU Card Sweep (128GB VRAM / 2 GCDs) ==="
echo "=========================================================================="
echo "Job Array Task ID: $SLURM_ARRAY_TASK_ID"
echo "Host Node: $SLURM_NODENAME"
echo "Allocated Hardware: 1 Full Physical MI250X Card (2x GCDs, 128 GB HBM2e VRAM)"
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

echo "=== Launching 22,500-packet sweep on 1 Full Physical MI250X (128GB VRAM) for Repetition ${RUN_NUM}/10 (${SUFFIX}) ==="
python3 run_matrix.py \
  --max-packets-per-api 2500 \
  --chaos-rate 0.10 \
  --repetitions 1 \
  --phases fast,bert,gemma \
  --run-number $RUN_NUM \
  --suffix "${SUFFIX}" \
  --packets-file data/ingested/telemetry_clean_bench_22500.json

echo "=========================================================================="
echo "=== Completed Repetition ${RUN_NUM}/10 on 1 Full Physical MI250X Card ==="
echo "End time: $(date)"
echo "=========================================================================="
