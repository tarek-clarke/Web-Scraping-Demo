#!/bin/bash
# Deterministic one-GPU stream replay for GH200/B300/other CUDA hosts.
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$PROJECT_ROOT"

if [ -x .venv-accelerator/bin/python ]; then
    PYTHON=.venv-accelerator/bin/python
elif [ -x .venv-spheron/bin/python ]; then
    PYTHON=.venv-spheron/bin/python
else
    echo "ERROR: no accelerator environment; run bash scripts/bootstrap_accelerator_env.sh" >&2
    exit 1
fi

STREAM="${RAP_STREAM_FILE:-data/replay/telemetry_frozen_22500_v8.jsonl}"
if [ ! -f "$STREAM" ]; then
    "$PYTHON" scripts/build_frozen_telemetry_stream.py --output "$STREAM"
fi

TAG="${RAP_HARDWARE_TAG:-nvidia}"
RATE="${RAP_STREAM_RATE_PPS:-0}"
BATCH="${RAP_STREAM_BATCH_SIZE:-16}"
REPETITIONS="${RAP_STREAM_REPETITIONS:-3}"
METHODS="${RAP_STREAM_METHODS:-minilm qwen_1_5b bge}"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUTPUT="${RAP_STREAM_OUTPUT_DIR:-data/reports/frozen_stream_${TAG}_${STAMP}}"

# shellcheck disable=SC2086
"$PYTHON" scripts/run_frozen_telemetry_stream.py \
    --stream "$STREAM" \
    --methods $METHODS \
    --rate-pps "$RATE" \
    --consumer-batch-size "$BATCH" \
    --repetitions "$REPETITIONS" \
    --hardware-profile cuda \
    --require-accelerator \
    --require-energy-telemetry \
    --output-dir "$OUTPUT"
