#!/bin/bash
#SBATCH --job-name=vqc-select
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=02:00:00
#SBATCH --output=vqc_select_%j.out
#SBATCH --error=vqc_select_%j.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$PROJECT_ROOT"
source "$PROJECT_ROOT/scripts/lumi_cache_env.sh"

module purge
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.11.7
if module is-loaded PrgEnv-cray >/dev/null 2>&1; then
    module swap PrgEnv-cray PrgEnv-gnu
else
    module load PrgEnv-gnu
fi
module load lumi-CrayPath

TRAIN_ENV="${RAP_LUMI_TRAIN_ENV:-$PROJECT_ROOT/.venv-aer-lumi}"
if [ ! -f "$TRAIN_ENV/bin/activate" ]; then
    echo "ERROR: missing isolated LUMI Aer environment: $TRAIN_ENV" >&2
    echo "Run bash scripts/bootstrap_lumi_aer_env.sh first." >&2
    exit 1
fi
source "$TRAIN_ENV/bin/activate"
echo "Training environment: $TRAIN_ENV"
python3 -m pip check
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export RAP_REQUIRE_GPU_TELEMETRY=1
export IS_LUMI=1
if [[ ! "${SLURM_JOB_GPUS:-}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: expected one scheduler-assigned GCD ID, got '${SLURM_JOB_GPUS:-unset}'" >&2
    exit 1
fi
export RAP_ASSIGNED_GPU_ID="$SLURM_JOB_GPUS"
: "${RAP_TRAIN_JOB_ID:?RAP_TRAIN_JOB_ID must identify the completed training array}"

python3 scripts/preflight_accelerator.py \
    --expected-devices 1 \
    --profile training \
    --accelerator-runtime aer \
    --require-aer \
    --require-router-qnn \
    --json-output "data/training/preflight_select_${SLURM_JOB_ID}.json"

python3 scripts/run_with_energy.py \
    --csv "data/training/energy_select_${LUMI_GPU_PROFILE//-/_}_${SLURM_JOB_ID}.csv" \
    --summary "data/training/energy_select_${LUMI_GPU_PROFILE//-/_}_${SLURM_JOB_ID}.json" \
    --label "lumi-vqc-select-${LUMI_GPU_PROFILE}" -- \
    python3 -u scripts/train_qpu_router.py select \
        --oracle "${ORACLE:-data/training/router_oracle_22500_v5_${LUMI_GPU_PROFILE//-/_}.jsonl}" \
        --candidates-dir "data/training/qpu_router_multistart_v5_${LUMI_GPU_PROFILE//-/_}" \
        --model-output "configs/quantum_router_v5_${LUMI_GPU_PROFILE//-/_}.json" \
        --expected-starts 10 \
        --backend aer_gpu \
        --evaluation-shots 2048 \
        --min-macro-f1 0.70 \
        --min-balanced-accuracy 0.70

shopt -s nullglob
ORACLE_STEM="${ORACLE:-data/training/router_oracle_22500_v5_${LUMI_GPU_PROFILE//-/_}.jsonl}"
ORACLE_STEM="${ORACLE_STEM%.jsonl}"
ENERGY_INPUTS=(
    "${ORACLE_STEM}".part_*.energy_summary.json
    data/training/energy_train_${LUMI_GPU_PROFILE//-/_}_${RAP_TRAIN_JOB_ID}_*.json
    "data/training/energy_select_${LUMI_GPU_PROFILE//-/_}_${SLURM_JOB_ID}.json"
)
if [ "${#ENERGY_INPUTS[@]}" -lt 11 ]; then
    echo "ERROR: expected at least ten training and one selection energy summary; found ${#ENERGY_INPUTS[@]}" >&2
    exit 1
fi
python3 scripts/summarize_energy.py \
    --output-prefix "data/training/energy_summary_${LUMI_GPU_PROFILE//-/_}_${RAP_TRAIN_JOB_ID}" \
    --inputs "${ENERGY_INPUTS[@]}"
