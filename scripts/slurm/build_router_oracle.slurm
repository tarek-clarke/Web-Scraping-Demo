#!/bin/bash
#SBATCH --job-name=router-oracle
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --time=36:00:00
#SBATCH --output=router_oracle_%j.out
#SBATCH --error=router_oracle_%j.err

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$PROJECT_ROOT"

# Keep model and tokenizer caches on the project scratch filesystem.
CACHE_ROOT="${PROJECT_ROOT}/.cache"
export XDG_CACHE_HOME="$CACHE_ROOT"
export HF_HOME="${CACHE_ROOT}/huggingface"
export HF_DATASETS_CACHE="${HF_HOME}/datasets"
export TRANSFORMERS_CACHE="${HF_HOME}/transformers"
mkdir -p "$HF_DATASETS_CACHE" "$TRANSFORMERS_CACHE"

module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings

LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
if [ ! -r "$LUMI_SIF" ]; then
    echo "ERROR: LUMI ROCm container not readable: $LUMI_SIF" >&2
    exit 1
fi
PYTHON_BIN=(singularity run "$LUMI_SIF" python)

export HF_TORCH_DTYPE=bfloat16
export TOKENIZERS_PARALLELISM=false

EXPECTED_GCDS=2
[ "${LUMI_GPU_PROFILE:-single}" = "full-node" ] && EXPECTED_GCDS=8
if [ "${SLURM_GPUS_ON_NODE:-}" != "$EXPECTED_GCDS" ]; then
    echo "ERROR: expected $EXPECTED_GCDS LUMI GCDs for profile ${LUMI_GPU_PROFILE:-single}, got '${SLURM_GPUS_ON_NODE:-unset}'" >&2
    exit 1
fi
"${PYTHON_BIN[@]}" - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("ERROR: GPU oracle requested but torch.cuda.is_available() is false")
print(f"LUMI accelerator preflight: {torch.cuda.device_count()} visible device(s)")
PY

"${PYTHON_BIN[@]}" -u scripts/build_router_oracle.py \
    --packets-file data/ingested/telemetry_clean_bench_22500.json \
    --output data/training/router_oracle_22500_v3.jsonl \
    --max-packets-per-api 2500 \
    --chunk-size 64 \
    --batch-size 64 \
    --accuracy-sla 0.95 \
    --resume
