#!/bin/bash
#SBATCH --job-name=local_embed_10runs
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=02:00:00
#SBATCH --output=logs/local_embed_10runs_%j.out
#SBATCH --error=logs/local_embed_10runs_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-framework"
cd "$PROJECT_ROOT" || exit 1

echo "=========================================================================="
echo "=== Local GPU Embedding 10-Repetition Benchmark Sweep (LUMI-G) ==="
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

mkdir -p logs

for r in $(seq 1 10); do
  suffix="_bge_embed_run$(printf '%02d' $r)"
  echo "=== Launching Local GPU Embedding Repetition ${r}/10 (${suffix}) ==="
  python3 run_matrix.py \
    --max-packets-per-api 2500 \
    --chaos-rate 0.10 \
    --repetitions 1 \
    --phases bert \
    --run-number $r \
    --suffix "${suffix}" \
    --packets-file data/ingested/telemetry_clean_bench_22500.json
done

echo "=========================================================================="
echo "=== Completed 10 Local GPU Embedding Repetitions on LUMI-G ==="
echo "End time: $(date)"
echo "=========================================================================="
