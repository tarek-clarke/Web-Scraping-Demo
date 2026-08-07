#!/bin/bash
#SBATCH --job-name=classical_router_bench
#SBATCH --account=project_465002996
#SBATCH --partition=small
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --output=classical_router_%j.out
#SBATCH --error=classical_router_%j.err

echo "=== CLASSICAL ROUTER CPU BENCHMARK RUN ==="
echo "Node: $(hostname)"
echo "Date: $(date)"

module purge
module load LUMI/24.03 partition/L
module load Python/3.11.7-cortex-a57

cd /scratch/project_465002996/clarketa/resilient-rap-framework

export PYTHONPATH=.

python3 -u scripts/run_classical_router_experiment.py

echo "=== CLASSICAL ROUTER RUN COMPLETE ==="
