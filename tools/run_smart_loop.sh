#!/bin/bash
# Smart Benchmark Loop - Runs the benchmark suite until exactly exactly N (default: 3) runs exist.

# Ensure we have our toolset
if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python3 -m pip install -r requirements.txt --quiet
python3 setup.py build_ext --inplace --quiet

# Detect the precise hardware name matching the Python scripts
HW_NAME=$(python3 tools/get_hardware_name.py)
HW_DIR="data/reports/$HW_NAME/"

# Ensure the directory exists so ls doesn't fail
mkdir -p "$HW_DIR"

# Count the number of sprint reports as an indicator of full suite completions
# Look specifically for telemetry_gpu_stress_test_report_sprint_*.json
EXISTING=$(ls ${HW_DIR}telemetry_gpu_stress_test_report_sprint_*.json 2>/dev/null | wc -l)

TARGET_RUNS=${1:-3}
REMAINDER=$((TARGET_RUNS - EXISTING))

echo "=========================================================="
echo "🎯 SMART BENCHMARK LOOP"
echo "Hardware: $HW_NAME"
echo "Target Runs: $TARGET_RUNS"
echo "Existing Runs: $EXISTING"
echo "=========================================================="

if [ $REMAINDER -le 0 ]; then
    echo "✅ Target of $TARGET_RUNS runs has already been met or exceeded. Exiting."
    exit 0
fi

echo "🚀 Need $REMAINDER more runs. Entering loop..."

for ((i=1; i<=REMAINDER; i++)); do
    echo ""
    echo "🏁 ------------------ RUN $(($EXISTING + $i)) / $TARGET_RUNS ------------------ 🏁"
    ./tools/run_all_benchmarks.sh "$HW_NAME"
done

echo "🎉 All $TARGET_RUNS configured runs have completed perfectly."
