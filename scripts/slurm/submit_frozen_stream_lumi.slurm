#!/bin/bash
# Deterministic one-GCD MI250X replay. CPU methods intentionally execute on
# the allocated host CPU; local semantic/LLM methods must execute on ROCm.
#SBATCH --job-name=rap-stream
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --time=08:00:00
#SBATCH --output=frozen_stream_%j.out
#SBATCH --error=frozen_stream_%j.err

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
cd "$PROJECT_ROOT"
source "$PROJECT_ROOT/scripts/lumi_cache_env.sh"

LUMI_SITE_PACKAGES="${RAP_LUMI_SITE_PACKAGES:-$PROJECT_ROOT/.runtime/lumi/site-packages}"
[ -d "$LUMI_SITE_PACKAGES" ] || { echo "ERROR: run bash scripts/bootstrap_lumi_runtime.sh first" >&2; exit 1; }
export PYTHONPATH="$LUMI_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
export SINGULARITYENV_PYTHONPATH="$PYTHONPATH"
export RAP_REQUIRE_GPU_TELEMETRY=1
export SINGULARITYENV_RAP_REQUIRE_GPU_TELEMETRY=1
export IS_LUMI=1
export SINGULARITYENV_IS_LUMI=1

module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings
LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
[ -r "$LUMI_SIF" ] || { echo "ERROR: LUMI container unavailable: $LUMI_SIF" >&2; exit 1; }

STREAM="${RAP_STREAM_FILE:-data/replay/telemetry_frozen_22500_v9.jsonl}"
RATE="${RAP_STREAM_RATE_PPS:-0}"
BATCH="${RAP_STREAM_BATCH_SIZE:-256}"
REPETITIONS="${RAP_STREAM_REPETITIONS:-3}"
METHODS="${RAP_STREAM_METHODS:-minilm qwen_1_5b bge cross_encoder}"
LIMIT="${RAP_STREAM_LIMIT:-0}"
TAG="${RAP_HARDWARE_TAG:-mi250x_one_gcd}"
OUTPUT="${RAP_STREAM_OUTPUT_DIR:-data/reports/frozen_stream_${TAG}_${SLURM_JOB_ID}}"
LIMIT_ARGS=()
if [ "$LIMIT" -gt 0 ]; then
    LIMIT_ARGS=(--limit "$LIMIT")
fi

if [ ! -f "$STREAM" ]; then
    singularity exec "$LUMI_SIF" python scripts/build_frozen_telemetry_stream.py --output "$STREAM"
fi

singularity exec "$LUMI_SIF" python - <<'PY'
import torch
if not torch.cuda.is_available() or not torch.version.hip:
    raise SystemExit("ERROR: ROCm accelerator unavailable; CPU fallback forbidden")
if torch.cuda.device_count() != 1:
    raise SystemExit(f"ERROR: expected one scheduler-bound GCD, saw {torch.cuda.device_count()}")
print("ROCm stream device:", torch.cuda.get_device_name(0), flush=True)
PY

# shellcheck disable=SC2086
singularity exec "$LUMI_SIF" python scripts/run_frozen_telemetry_stream.py \
    --stream "$STREAM" \
    --methods $METHODS \
    --rate-pps "$RATE" \
    --consumer-batch-size "$BATCH" \
    --repetitions "$REPETITIONS" \
    "${LIMIT_ARGS[@]}" \
    --hardware-profile rocm \
    --require-accelerator \
    --require-energy-telemetry \
    --output-dir "$OUTPUT"
