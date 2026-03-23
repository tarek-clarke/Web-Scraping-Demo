#!/bin/bash
# =============================================================================
#  Team Testing — Local Parallel Concurrency Wrapper (Non-Docker)
# =============================================================================
#  Launches two parallel telemetry-gpu-stress-test runs on the local machine
#  to validate resilience under multi-car load without Docker.
# =============================================================================

set -e

# Default parameters
PACKETS=${1:-2000}
CHAOS=${2:-0.15}
RUN_SUFFIX=${3:-""}

echo "🏁 STARTING LOCAL TEAM TEST: Two Cars | Single GPU/CPU"
echo "--- Configuration ---"
echo "Packets: $PACKETS"
echo "Chaos:   $CHAOS"
echo "Suffix:  $RUN_SUFFIX"
echo "---------------------"

# Ensure environment is ready
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
export PYTHONPATH="."

# Launch Parallel Stress Tests
echo "⚡ Launching Car 1 Benchmark..."
python3 tools/telemetry_gpu_stress_test.py --packets $PACKETS --chaos $CHAOS --output-suffix _car1${RUN_SUFFIX} --diagnostic &
CAR1_PID=$!

sleep 2

echo "⚡ Launching Car 2 Benchmark..."
python3 tools/telemetry_gpu_stress_test.py --packets $PACKETS --chaos $CHAOS --output-suffix _car2${RUN_SUFFIX} --diagnostic &
CAR2_PID=$!

# Wait for both to finish
echo "⏳ Monitoring parallel execution (PIDs: $CAR1_PID, $CAR2_PID)..."
wait $CAR1_PID
echo "✅ Car 1 Complete"
wait $CAR2_PID
echo "✅ Car 2 Complete"

echo "--------------------------------------------------------"
echo "🏆 LOCAL TEAM TEST COMPLETE"
echo "--------------------------------------------------------"
echo "Check data/reports/ for car1 and car2 JSON/CSV files."
echo "--------------------------------------------------------"
