#!/bin/bash
#SBATCH --job-name=rap-gpu-bind
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=2
#SBATCH --ntasks-per-node=2
#SBATCH --cpus-per-task=8
#SBATCH --time=00:10:00
#SBATCH --output=rap_gpu_bind_%j.out
#SBATCH --error=rap_gpu_bind_%j.err

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
cd "$PROJECT_ROOT"

module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings
LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
export PROJECT_ROOT LUMI_SIF
LUMI_SITE_PACKAGES="${RAP_LUMI_SITE_PACKAGES:-${PROJECT_ROOT}/.runtime/lumi/site-packages}"
if [ ! -d "$LUMI_SITE_PACKAGES" ]; then
    echo "ERROR: missing LUMI runtime layer; run bash scripts/bootstrap_lumi_runtime.sh" >&2
    exit 1
fi
export PYTHONPATH="$LUMI_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
export SINGULARITYENV_PYTHONPATH="$PYTHONPATH"

EXPECTED_GCDS="${SLURM_NTASKS:?}"
if [ "${SLURM_GPUS_ON_NODE:-}" != "$EXPECTED_GCDS" ]; then
    echo "ERROR: allocated ${SLURM_GPUS_ON_NODE:-0} GCDs for $EXPECTED_GCDS tasks" >&2
    exit 1
fi
GPU_MAP="${SLURM_JOB_GPUS:-}"
if [[ ! "$GPU_MAP" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
    echo "ERROR: unsupported SLURM_JOB_GPUS value: '$GPU_MAP'" >&2
    exit 1
fi
IFS=',' read -r -a GPU_IDS <<< "$GPU_MAP"
if [ "${#GPU_IDS[@]}" -ne "$EXPECTED_GCDS" ]; then
    echo "ERROR: Slurm granted ${#GPU_IDS[@]} GPU IDs for $EXPECTED_GCDS tasks" >&2
    exit 1
fi

srun --ntasks="$EXPECTED_GCDS" --gpus-per-task=1 --gpu-bind="map_gpu:$GPU_MAP" \
    --kill-on-bad-exit=1 \
    bash "$PROJECT_ROOT/scripts/slurm/run_accelerator_probe.sh"

echo "PASS: $EXPECTED_GCDS Slurm tasks each completed a real one-GPU bfloat16 probe."
