#!/bin/bash
# vlq_submit_all.sh
# Submits 10 sequential VLQ QPU benchmark runs from a LUMI login/CPU node.
# Mirrors submit_all.sh exactly, but targets VLQ-EU instead of LUMI's MI250X.
#
# Output folders will be:
#   data/reports/quantum_VLQ_QPU_10rep_success/quantum_VLQ_QPU_vlq_qpu_run_1/
#   data/reports/quantum_VLQ_QPU_10rep_success/quantum_VLQ_QPU_vlq_qpu_run_2/
#   ...
#
# Setup before running:
#   1. conda activate vlq
#   2. set -a && source .env.vlq && set +a   # loads VLQ_PROJECT / VLQ_RESOURCE
#   3. bash vlq_submit_all.sh
#
# The .env.vlq file is git-ignored.  Never put project IDs in this script.

set -e

PROJECT_DIR="/scratch/project_465002996/clarketa/resilient-rap-quantum"
REPORTS_BASE="data/reports"
CONDA_ENV="vlq"

# Validate credentials are loaded from environment (set via .env.vlq)
if [ -z "$VLQ_PROJECT" ] || [ -z "$VLQ_RESOURCE" ]; then
    echo "ERROR: VLQ_PROJECT and VLQ_RESOURCE must be set."
    echo "  set -a && source .env.vlq && set +a"
    exit 1
fi

echo "=== Submitting 10 VLQ QPU repetition runs ==="
echo "  Project  : $VLQ_PROJECT"
echo "  Resource : $VLQ_RESOURCE"
echo ""

for run_idx in {1..10}
do
    job_file="vlq_run_${run_idx}.slurm"
    run_suffix="_run_${run_idx}"

    echo "Creating Slurm job for VLQ repetition ${run_idx}..."

    cat <<EOT > ${job_file}
#!/bin/bash
#SBATCH --job-name=vlq-r${run_idx}
#SBATCH --account=project_465002996
#SBATCH --partition=small          # CPU-only partition — QPU is accessed remotely
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=06:00:00            # 6 hr wall — ~16 min QPU + queue headroom
#SBATCH --output=vlq_rep_${run_idx}_%j.out
#SBATCH --error=vlq_rep_${run_idx}_%j.err

echo "=== VLQ QPU Repetition Run ${run_idx} ==="
echo "Node: \$SLURM_NODENAME"
echo "Start: \$(date)"

# Load minimal LUMI modules (no GPU needed — QPU is remote)
module load LUMI/25.09
module load cray-python/3.10.10

# Activate VLQ conda environment
source /appl/local/csc/soft/ai/miniconda/etc/profile.d/conda.sh
conda activate ${CONDA_ENV}

cd ${PROJECT_DIR}

# Load VLQ credentials from local git-ignored file
if [ -f .env.vlq ]; then
    set -a && source .env.vlq && set +a
else
    echo "ERROR: .env.vlq not found at ${PROJECT_DIR}/.env.vlq"
    exit 1
fi

# Run smoke test on rep 1 only — abort the full batch if it fails
if [ "${run_idx}" = "1" ]; then
    echo "--- Smoke test (rep 1 only) ---"
    python3 vlq_smoke_test.py || { echo "SMOKE TEST FAILED. Aborting."; exit 1; }
fi

# Run benchmark matrix sweep (quantum phase only — fast/bert/gemma already benchmarked on LUMI)
echo "Running VLQ quantum routing sweep..."
python3 run_matrix.py \
  --max-packets-per-api 2500 \
  --chaos-rate 0.10 \
  --repetitions 1 \
  --phases quantum \
  --backend vlq \
  --suffix "${run_suffix}"

echo "End: \$(date)"
EOT

    sbatch ${job_file}
    rm ${job_file}
    sleep 2   # Stagger submissions so LEXIS auth windows don't overlap
done

echo ""
echo "=== All 10 VLQ jobs submitted. ==="
echo "Results will appear in:"
echo "  ${PROJECT_DIR}/${REPORTS_BASE}/quantum_VLQ_QPU_vlq_qpu_run_N/"
echo ""
echo "Monitor with: squeue -u \$USER"
