#!/bin/bash
set -e

# --- Resilient RAP Universal Benchmark Suite ---
# Usage: ./tools/run_all_benchmarks.sh [HARDWARE_NAME]
# If HARDWARE_NAME is omitted, it will try to auto-detect.

echo "🏎️ Initializing Resilient RAP Benchmark Suite..."

# 1. Environment Setup
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate
python3 -m pip install --upgrade pip

# Detect the host accelerator/compiler setup before dependency installation.
if [ -f ./init_phd_env.sh ]; then
    # shellcheck disable=SC1091
    source ./init_phd_env.sh
fi

# 2. Dependencies
echo "🔗 Installing/Verifying Dependencies..."
python3 -m pip install -r requirements.txt

case "${RAP_BUILD_BACKEND:-cpu}" in
    cuda)
        python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
        ;;
    rocm)
        python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2
        ;;
    mps|cpu|*)
        python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
        ;;
esac

# 3. Build Extensions
echo "🏭 Building C++ Ingest Extensions..."
python3 setup.py build_ext --inplace

# 4. Hardware Detection (Matched to Python _sanitize_suffix_token logic)
DETECTED_GPU=$(python3 -c "import torch, re; name = torch.cuda.get_device_name(0).replace('NVIDIA ', '') if torch.cuda.is_available() else 'CPU_Fallback'; print(re.sub(r'[^A-Za-z0-9]+', '', name))" 2>/dev/null || echo "UnknownHardware")
HARDWARE_NAME=${1:-$DETECTED_GPU}
# Ensure the final name is sanitized even if passed as an argument
HARDWARE_NAME=$(python3 -c "import re; print(re.sub(r'[^A-Za-z0-9]+', '', '$HARDWARE_NAME'))")
export RAP_OUTPUT_SUFFIX=$HARDWARE_NAME

echo "📍 Benchmarking on: $HARDWARE_NAME"

# 5. The Suite (Sprint: 30K total, Weekend: 3.6M total)
# NOTE: --packets is PER SESSION (×15 sessions). Use 2000 for 30K total, 240000 for 3.6M total.
echo "🚦 Starting Full Suite (3 runs per test + telemetry + engine stress)..."

run_benchmark() {
    local run_cmd="$1"
    local label="$2"

    echo "▶ Running $label"
    eval "$run_cmd"
}

# Canonical Profiles (5% mixed chaos)
run_benchmark 'PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.05 --output-suffix _sprint' "Sprint"
run_benchmark 'PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.05 --output-suffix _weekend' "Weekend"

# Triple-header baseline stress test
run_benchmark 'PYTHONPATH="." python3 tools/telemetry_stress_test.py --packets 5000 --chaos 0.20' "Triple-header stress test"

# Repair-Focus Profiles (0.5% targeted chaos)
run_benchmark 'PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.005 --chaos-profile repair_focus --output-suffix _sprint_repairfocus' "Repair-focus Sprint"
run_benchmark 'PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.005 --chaos-profile repair_focus --output-suffix _weekend_repairfocus' "Repair-focus Weekend"

# Ultra-Low / Jitter Stress (0.1% micro-faults)
run_benchmark 'PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.001 --chaos-profile repair_focus --output-suffix _sprint_ultralow' "Ultralow Sprint"
run_benchmark 'PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.001 --chaos-profile repair_focus --output-suffix _weekend_ultralow' "Ultralow Weekend"

# Diagnostic Deep-Dive (High-friction fault load)
run_benchmark 'PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 4000 --chaos 0.12 --chaos-profile balanced --diagnostic --output-suffix _diagnostic' "Diagnostic"

# Engine temperature stress test (7900XT / M4-compatible)
run_benchmark 'PYTHONPATH="." python3 tools/stress_test_engine_temp.py' "Engine temperature stress test"

# 5b. Canonicalize benchmark output layout to match archived reports
echo "🗂️ Organizing benchmark files into canonical data/reports layout..."
python3 tools/organize_data.py

# 6. Finalization & Automated Push
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="data/reports/$HARDWARE_NAME"
RUN_STATE_DIR="$REPORT_DIR/_meta/completed_runs"
mkdir -p "$RUN_STATE_DIR"
RUN_INDEX="${RAP_RUN_INDEX:-}"
if [ -z "$RUN_INDEX" ]; then
        RUN_INDEX=$(find "$RUN_STATE_DIR" -maxdepth 1 -type f -name 'run_*.json' 2>/dev/null | wc -l | tr -d ' ')
        RUN_INDEX=$((RUN_INDEX + 1))
fi

RUN_MARKER="$RUN_STATE_DIR/run_$(printf '%03d' "$RUN_INDEX").json"
cat > "$RUN_MARKER" <<EOF
{
    "hardware": "$HARDWARE_NAME",
    "run_index": $RUN_INDEX,
    "timestamp": "$TIMESTAMP",
    "backend": "${RAP_BUILD_BACKEND:-unknown}",
    "status": "complete"
}
EOF

echo "📦 Packaging Results..."
tar -czf ${HARDWARE_NAME}_results_${TIMESTAMP}.tar.gz $REPORT_DIR/

echo "📤 Synchronizing and pushing results to GitHub..."
git add $REPORT_DIR/
git commit -m "docs: add $HARDWARE_NAME benchmark results ($TIMESTAMP)"

# Pull latest remote changes (rebase) to avoid conflicts if another instance pushed first
git pull --rebase origin main || true

# Push. Use '|| true' gently so if an extreme race condition occurs, we don't crash the loop.
git push origin main || echo "⚠️ Push collision gracefully skipped. Will retry next loop."

echo "✅ ALL BENCHMARKS COMPLETE AND PUSHED TO REMOTE."
echo "Local archive: ${HARDWARE_NAME}_results_${TIMESTAMP}.tar.gz"
