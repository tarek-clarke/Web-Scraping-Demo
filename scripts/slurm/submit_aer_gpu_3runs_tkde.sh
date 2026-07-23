#!/bin/bash
# Submits 10 concurrent LUMI GPU benchmark runs for the TKDE 9-API corpus.
# The runs are gated on a successful ROCm Aer rebuild/preflight job.
#
# Output folders:
#   data/reports/quantum_run_lumi_aer_2026-07-22_run01/
#   data/reports/quantum_run_lumi_aer_2026-07-22_run02/
#   data/reports/quantum_run_lumi_aer_2026-07-22_run03/
#   data/reports/quantum_run_lumi_aer_2026-07-22_run04/
#   data/reports/quantum_run_lumi_aer_2026-07-22_run05/
#   data/reports/quantum_run_lumi_aer_2026-07-22_run06/
#   data/reports/quantum_run_lumi_aer_2026-07-22_run07/
#   data/reports/quantum_run_lumi_aer_2026-07-22_run08/
#   data/reports/quantum_run_lumi_aer_2026-07-22_run09/
#   data/reports/quantum_run_lumi_aer_2026-07-22_run10/

set -e

PROJECT_DIR="/scratch/project_465002996/clarketa/resilient-rap-tkde-aer-20260722"
RUN_DATE="2026-07-22"
MAX_PACKETS_PER_API=2500
CHAOS_RATE="0.10"

echo "=== Submitting 10 LUMI Aer GPU benchmark runs (small-g, 10 GPUs if available) ==="
echo "  Project dir : ${PROJECT_DIR}"
echo "  Run date    : ${RUN_DATE}"
echo "  Chaos rate  : ${CHAOS_RATE}"
echo "  Packets/API : ${MAX_PACKETS_PER_API}"
echo ""

build_job_id=$(PROJECT_DIR="${PROJECT_DIR}" sbatch scripts/slurm/rebuild_aer_rocm_tkde.slurm | awk '{print $4}')

if [ -z "${build_job_id}" ]; then
    echo "ERROR: failed to submit Aer rebuild/preflight job."
    exit 1
fi

echo "Aer rebuild/preflight job: ${build_job_id}"
echo ""

for run_idx in 1 2 3 4 5 6 7 8 9 10
do
    job_file="aer_gpu_run_${run_idx}.slurm"
    run_suffix="_${RUN_DATE}_run$(printf '%02d' "${run_idx}")"

    cat <<EOT > "${job_file}"
#!/bin/bash
#SBATCH --job-name=aer-r${run_idx}
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=60G
#SBATCH --time=08:00:00
#SBATCH --output=aer_run_${run_idx}_%j.out
#SBATCH --error=aer_run_${run_idx}_%j.err

set -euo pipefail

module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10
source /scratch/project_465002996/clarketa/vlq-env/bin/activate

cd ${PROJECT_DIR}
export PYTHONPATH="${PROJECT_DIR}"
export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache
export CHAOS_DEVICE=cuda:0

python3 run_matrix.py \
  --max-packets-per-api ${MAX_PACKETS_PER_API} \
  --chaos-rate ${CHAOS_RATE} \
  --repetitions 1 \
  --phases quantum \
  --backend aer_gpu \
  --run-date ${RUN_DATE} \
  --run-number ${run_idx} \
  --suffix "${run_suffix}" \
  --packets-file data/ingested/telemetry_clean_bench_22500.json
EOT

    sbatch --dependency=afterok:${build_job_id} "${job_file}"
    rm "${job_file}"
    sleep 2
done

echo "=== All 10 Aer GPU jobs submitted. ==="
