#!/bin/bash
set -e

# Smart Benchmark Loop - Runs the benchmark suite until exactly N (default: 3) runs exist.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Ensure we have our toolset
if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python3 -m pip install -r requirements.txt --quiet
python3 setup.py build_ext --inplace --quiet

TARGET_RUNS=${1:-3}
HW_NAME=${2:-$(python3 tools/get_hardware_name.py)}
REPORT_ROOT="data/reports/$HW_NAME"
STRICT_MARKER_DIR="$REPORT_ROOT/_meta/completed_runs"
CANONICAL_SUMMARY_GLOB="telemetry_stress_test_report_${HW_NAME}*.json"

# Ensure the directory exists so ls doesn't fail
mkdir -p "$REPORT_ROOT"
mkdir -p "$STRICT_MARKER_DIR"

# Normalize any straggler outputs before counting so the loop sees the canonical layout.
python3 tools/organize_data.py >/dev/null 2>&1 || true

BACKFILL_COUNT=$(find "$STRICT_MARKER_DIR" -maxdepth 1 -type f -name 'run_*.json' 2>/dev/null | wc -l | tr -d ' ')
if [ "$BACKFILL_COUNT" -eq 0 ]; then
    LEGACY_COUNT=$(find "$REPORT_ROOT" -maxdepth 1 -type f -name "$CANONICAL_SUMMARY_GLOB" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$LEGACY_COUNT" -gt 0 ]; then
        for run_index in $(seq 1 "$LEGACY_COUNT"); do
            marker_path="$STRICT_MARKER_DIR/run_$(printf '%03d' "$run_index").json"
            cat > "$marker_path" <<EOF
{
  "hardware": "$HW_NAME",
  "run_index": $run_index,
  "source": "legacy-backfill",
  "status": "complete"
}
EOF
        done
    fi
fi

# Count strict completion markers, not loose result files.
EXISTING=$(find "$STRICT_MARKER_DIR" -maxdepth 1 -type f -name 'run_*.json' 2>/dev/null | wc -l | tr -d ' ')

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
    RAP_RUN_INDEX=$(($EXISTING + $i)) ./tools/run_all_benchmarks.sh "$HW_NAME"
    python3 tools/organize_data.py >/dev/null 2>&1 || true
done

echo "🎉 All $TARGET_RUNS configured runs have completed perfectly."
