#!/bin/bash
set -euo pipefail

: "${PROJECT_ROOT:?PROJECT_ROOT is required}"
: "${RAP_STREAM_OUTPUT_DIR:?RAP_STREAM_OUTPUT_DIR is required}"
: "${SLURM_PROCID:?SLURM_PROCID is required}"
: "${SLURM_NTASKS:?SLURM_NTASKS is required}"

cd "$PROJECT_ROOT"
source "$PROJECT_ROOT/scripts/lumi_cache_env.sh"
LUMI_SITE_PACKAGES="${RAP_LUMI_SITE_PACKAGES:-$PROJECT_ROOT/.runtime/lumi/site-packages}"
[ -d "$LUMI_SITE_PACKAGES" ] || { echo "ERROR: missing LUMI runtime" >&2; exit 1; }
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
[ -r "$LUMI_SIF" ] || { echo "ERROR: unavailable container: $LUMI_SIF" >&2; exit 1; }

STREAM="${RAP_STREAM_FILE:-data/replay/telemetry_frozen_22500_v9.jsonl}"
METHODS="${RAP_STREAM_METHODS:-minilm qwen_1_5b bge}"
BATCH="${RAP_STREAM_BATCH_SIZE:-256}"
REPETITIONS="${RAP_STREAM_REPETITIONS:-3}"
SHARD_OUTPUT="$RAP_STREAM_OUTPUT_DIR/shards/shard_$SLURM_PROCID"

singularity exec "$LUMI_SIF" python - <<'PY'
import torch
if not torch.cuda.is_available() or not torch.version.hip or torch.cuda.device_count() != 1:
    raise SystemExit(f"ERROR: each shard requires exactly one ROCm GCD; saw {torch.cuda.device_count()}")
print("Bound ROCm GCD:", torch.cuda.get_device_name(0), flush=True)
PY

# shellcheck disable=SC2086
singularity exec "$LUMI_SIF" python scripts/run_frozen_telemetry_stream.py \
    --stream "$STREAM" --methods $METHODS --consumer-batch-size "$BATCH" \
    --repetitions "$REPETITIONS" --hardware-profile rocm --require-accelerator \
    --require-energy-telemetry --shard-index "$SLURM_PROCID" --shard-count "$SLURM_NTASKS" \
    --output-dir "$SHARD_OUTPUT"
