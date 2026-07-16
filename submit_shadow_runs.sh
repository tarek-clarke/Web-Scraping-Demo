#!/bin/bash
# Submits 10 sequential shadow routing runs.
# Output folders will be:
#   data/reports/shadow_routing_10rep/run_1/
#   data/reports/shadow_routing_10rep/run_2/
#   ...

set -e

PROJECT_DIR="/scratch/project_465002996/clarketa/resilient-rap-quantum"
REPORTS_BASE="data/reports/shadow_routing_10rep"

echo "=== Submitting 10 Shadow Routing runs ==="

for run_idx in {1..10}
do
    job_file="shadow_run_${run_idx}.slurm"
    out_dir="${REPORTS_BASE}/run_${run_idx}"

    echo "Creating Slurm job for shadow repetition ${run_idx}..."

    cat <<EOT > ${job_file}
#!/bin/bash
#SBATCH --job-name=shadow-r${run_idx}
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --time=02:00:00
#SBATCH --signal=B:TERM@120
#SBATCH --output=shadow_rep_${run_idx}_%j.out
#SBATCH --error=shadow_rep_${run_idx}_%j.err

echo "=== Shadow Routing Run ${run_idx} ==="
echo "Node: \$SLURM_NODENAME"
echo "Start: \$(date)"

# Load modules
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate venv
source "${PROJECT_DIR}/.venv-lumi/bin/activate"

export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache
export CHAOS_DEVICE=cuda:0

cd ${PROJECT_DIR}

echo "Running live_gpu_decoder.py with shadow routing..."
python3 -u live_gpu_decoder.py \\
  --reconciler quantum \\
  --chaos-rate 0.10 \\
  --shadow-routing \\
  --no-skip \\
  --max-packets 25000 \\
  --telemetry-file data/ingested/telemetry_clean_bench_25000.json \\
  --output-dir ${out_dir}

echo "End: \$(date)"
EOT

    sbatch ${job_file} || echo "WARNING: sbatch failed, are you on a login node?"
    rm ${job_file}
    sleep 2
done

echo ""
echo "=== All 10 shadow routing jobs submitted. ==="
echo "Results will appear in:"
echo "  ${PROJECT_DIR}/${REPORTS_BASE}/run_N/"
echo ""
