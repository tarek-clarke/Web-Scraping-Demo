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

# 2. Dependencies
echo "🔗 Installing/Verifying Dependencies..."
python3 -m pip install -r requirements.txt
python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# 3. Build Extensions
echo "🏭 Building C++ Ingest Extensions..."
python3 setup.py build_ext --inplace

# 4. Hardware Detection
DETECTED_GPU=$(python3 -c "import torch; print(torch.cuda.get_device_name(0).replace(' ', '_').replace('NVIDIA_', '') if torch.cuda.is_available() else 'CPU_Fallback')" 2>/dev/null || echo "Unknown_Hardware")
HARDWARE_NAME=${1:-$DETECTED_GPU}
export RAP_OUTPUT_SUFFIX=$HARDWARE_NAME

echo "📍 Benchmarking on: $HARDWARE_NAME"

# 5. The Suite (Sprint: 30K total, Weekend: 3.6M total)
# NOTE: --packets is PER SESSION (×15 sessions). Use 2000 for 30K total, 240000 for 3.6M total.
echo "🚦 Starting Full Suite (6 Tests + Diagnostic)..."

# Canonical Profiles (5% mixed chaos)
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.05 --output-suffix _sprint
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.05 --output-suffix _weekend

# Repair-Focus Profiles (0.5% targeted chaos)
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.005 --chaos-profile repair_focus --output-suffix _sprint_repairfocus
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.005 --chaos-profile repair_focus --output-suffix _weekend_repairfocus

# Ultra-Low / Jitter Stress (0.1% micro-faults)
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.001 --chaos-profile repair_focus --output-suffix _sprint_ultralow
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.001 --chaos-profile repair_focus --output-suffix _weekend_ultralow

# Diagnostic Deep-Dive (High-friction fault load)
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 4000 --chaos 0.12 --chaos-profile balanced --diagnostic --output-suffix _diagnostic

# 6. Finalization & Automated Push
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="data/reports/$HARDWARE_NAME"

echo "📦 Packaging Results..."
tar -czf ${HARDWARE_NAME}_results_${TIMESTAMP}.tar.gz $REPORT_DIR/

echo "📤 Pushing results to GitHub..."
git add $REPORT_DIR/
git commit -m "docs: add $HARDWARE_NAME benchmark results ($TIMESTAMP)"
git push origin main

echo "✅ ALL BENCHMARKS COMPLETE AND PUSHED TO REMOTE."
echo "Local archive: ${HARDWARE_NAME}_results_${TIMESTAMP}.tar.gz"
