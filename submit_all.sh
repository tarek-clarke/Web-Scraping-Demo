#!/bin/bash
# submit_all.sh - Runs 10 concurrent repetition jobs on LUMI's small-g partition.

set -e

PROJECT_DIR="/scratch/project_465002996/clarketa/resilient-rap-quantum"
REPORTS_BASE="data/reports"

echo "=== Submitting 10 Parallel Repetition runs to LUMI (small-g) ==="

for run_idx in {1..10}
do
    job_file="submit_run_${run_idx}.slurm"
    run_suffix="_run_${run_idx}"
    
    echo "Creating dynamic job config for Repetition ${run_idx}..."
    
    cat <<EOT > ${job_file}
#!/bin/bash
#SBATCH --job-name=q-route-r${run_idx}
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=60G
#SBATCH --time=08:00:00
#SBATCH --output=job_rep_${run_idx}_%j.out
#SBATCH --error=job_rep_${run_idx}_%j.err

echo "=== Quantum Repetition Run ${run_idx} ==="
echo "Node: \$SLURM_NODENAME"
echo "Allocated GPUs: \$SLURM_GPUS_ON_NODE"
echo "Start: \$(date)"

# Load modules
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate venv
source ${PROJECT_DIR}/.venv-lumi/bin/activate

# Environment variables
export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache
export CHAOS_DEVICE=cuda:0

# Step 1: Pre-train quantum router on this seed
echo "Training quantum router on historical seed..."
python3 -m src.routing.training --data data/reports/MI250X/ --output configs/trained_router_openf1.json --api openf1
python3 -m src.routing.training --data data/reports/MI250X/ --output configs/trained_router_finnhub.json --api finnhub
python3 -m src.routing.training --data data/reports/MI250X/ --output configs/trained_router_spacex.json --api spacex
python3 -m src.routing.training --data data/reports/MI250X/ --output configs/trained_router_openweather.json --api openweather

# Step 2: Run benchmark matrix sweep (single repetition loop instance)
echo "Running matrix sweep..."
python3 run_matrix.py \
  --max-packets-per-api 2500 \
  --chaos-rate 0.10 \
  --repetitions 1 \
  --phases fast,bert,gemma,quantum \
  --backend aer_simulator \
  --suffix "${run_suffix}"

echo "End: \$(date)"
EOT

    # Submit job to queue
    sbatch ${job_file}
    
    # Cleanup temporary local script file
    rm ${job_file}
done

echo "=== All 10 jobs submitted successfully! Check progress using squeue. ==="
