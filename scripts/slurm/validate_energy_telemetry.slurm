#!/bin/bash
#SBATCH --job-name=rap-energy-check
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --time=00:10:00
#SBATCH --output=rap_energy_check_%j.out
#SBATCH --error=rap_energy_check_%j.err

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
cd "$PROJECT_ROOT"

module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings
LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
LUMI_SITE_PACKAGES="${RAP_LUMI_SITE_PACKAGES:-${PROJECT_ROOT}/.runtime/lumi/site-packages}"
if [ ! -d "$LUMI_SITE_PACKAGES" ]; then
    echo "ERROR: missing LUMI runtime layer; run bash scripts/bootstrap_lumi_runtime.sh" >&2
    exit 1
fi
if [[ ! "${SLURM_JOB_GPUS:-}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: expected one scheduler-assigned GCD ID, got '${SLURM_JOB_GPUS:-unset}'" >&2
    exit 1
fi
export PYTHONPATH="$LUMI_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
export SINGULARITYENV_PYTHONPATH="$PYTHONPATH"
export RAP_ASSIGNED_GPU_ID="$SLURM_JOB_GPUS"
export RAP_REQUIRE_GPU_TELEMETRY=1
export IS_LUMI=1
export SINGULARITYENV_RAP_ASSIGNED_GPU_ID="$RAP_ASSIGNED_GPU_ID"
export SINGULARITYENV_RAP_REQUIRE_GPU_TELEMETRY=1
export SINGULARITYENV_IS_LUMI=1

echo "Assigned Slurm GCD: $RAP_ASSIGNED_GPU_ID"
for device_path in /sys/class/drm/card[0-9]*/device; do
    sensor="$(find "$device_path/hwmon" -name power1_average -print -quit 2>/dev/null || true)"
    printf 'DRM_DEVICE path=%s pci=%s power_sensor=%s\n' \
        "$device_path" "$(basename "$(readlink -f "$device_path")")" "${sensor:-none}"
done
if command -v rocm-smi >/dev/null 2>&1; then
    rocm-smi --showbus --showuniqueid --showpower --json || true
fi

CSV="data/training/preflight_energy_${SLURM_JOB_ID}.csv"
SUMMARY="data/training/preflight_energy_${SLURM_JOB_ID}.json"
singularity run "$LUMI_SIF" python scripts/run_with_energy.py \
    --csv "$CSV" --summary "$SUMMARY" --interval 0.5 \
    --label "lumi-energy-preflight" -- \
    python scripts/preflight_accelerator.py \
        --expected-devices 1 --profile oracle \
        --json-output "data/training/preflight_energy_accelerator_${SLURM_JOB_ID}.json"

singularity run "$LUMI_SIF" python - "$SUMMARY" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
telemetry = report["telemetry"]
assert report["status"] == "complete", report
assert telemetry["gpu_power_source"] == "amd_sysfs", telemetry
assert telemetry["gpu_energy_draw_joules"] > 0, telemetry
assert telemetry["samples_count"] >= 2, telemetry
print("PASS: measured LUMI GPU energy telemetry", telemetry)
PY
