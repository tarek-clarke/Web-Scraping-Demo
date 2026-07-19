#!/bin/bash
# Runs 10 sequential shadow routing runs locally using the virtual environment.

set -e

PROJECT_DIR="/Users/tarekclarke/resilient-rap-framework"
REPORTS_BASE="data/reports/shadow_routing_10rep"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python3"

echo "=== Starting 10 Local Shadow Routing runs ==="

for run_idx in {1..10}
do
    out_dir="${REPORTS_BASE}/run_${run_idx}"
    echo "Running local shadow repetition ${run_idx}..."
    
    # Run live_gpu_decoder.py locally
    $PYTHON_BIN -u live_gpu_decoder.py \
      --reconciler quantum \
      --chaos-rate 0.10 \
      --shadow-routing \
      --no-skip \
      --max-packets 25000 \
      --telemetry-file data/ingested/telemetry_clean_bench_25000.json \
      --output-dir ${out_dir}
      
    echo "Completed local shadow repetition ${run_idx}."
done

echo "=== All 10 local runs finished ==="
