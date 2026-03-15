#!/bin/bash
set -e

# --- B200 Benchmark Automated Suite ---
# Objective: Maximize value of high-cost compute hour with zero-touch execution.

echo "🚀 Starting B200 Execution Suite..."
export RAP_OUTPUT_SUFFIX=B200

# 1. Environment Setup
echo "📦 Setting up Python environment..."
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip

# 2. Dependencies
echo "🔗 Installing Core Dependencies..."
python3 -m pip install -r requirements.txt

echo "🧠 Installing NVIDIA Optimized PyTorch (CUDA 12.8)..."
python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# 3. Build Accelerated Extensions
echo "🏭 Building C++ Ingest Extensions..."
python3 setup.py build_ext --inplace

# 4. Canonical Benchmark Suite
echo "🏎️ Running Six-Benchmark Suite..."

# 1) Standard profile — Sprint
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.05 --output-suffix _sprint_B200

# 2) Standard profile — Weekend
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.05 --output-suffix _weekend_B200

# 3) Repair-focus realistic — Sprint
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.005 --chaos-profile repair_focus --output-suffix _sprint_repairfocus_B200

# 4) Repair-focus realistic — Weekend
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.005 --chaos-profile repair_focus --output-suffix _weekend_repairfocus_B200

# 5) Repair-focus ultralow — Sprint
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.001 --chaos-profile repair_focus --output-suffix _sprint_ultralow_B200

# 6) Repair-focus ultralow — Weekend
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.001 --chaos-profile repair_focus --output-suffix _weekend_ultralow_B200

# 5. Diagnostic Deep-Dive
echo "🔍 Running Diagnostic Attribution..."
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 60000 --chaos 0.12 --chaos-profile balanced --diagnostic --output-suffix _diagnostic_B200

# 6. Finalization
echo "📦 Packaging Results..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
tar -czf b200_benchmark_results_${TIMESTAMP}.tar.gz data/reports/B200/

echo "✅ ALL BENCHMARKS COMPLETE."
echo "File created: b200_benchmark_results_${TIMESTAMP}.tar.gz"
echo "Download with: scp user@host:$(pwd)/b200_benchmark_results_${TIMESTAMP}.tar.gz ."
