#!/bin/bash
# =============================================================================
#  Team Testing — Parallel Concurrency Wrapper
# =============================================================================
#  Launches two parallel telemetry-gpu-stress-test runs on the same GPU
#  to validate resilience under multi-car load.
# =============================================================================

set -e

# Default parameters
PACKETS=${1:-2000}
CHAOS=${2:-0.15}

echo "🏁 STARTING TEAM TEST: Two Cars | Single GPU"
echo "--- Configuration ---"
echo "Packets: $PACKETS"
echo "Chaos:   $CHAOS"
echo "---------------------"

# 1. Start Docker Containers
echo "🚀 Spinning up dedicated pipelines..."
docker-compose -f docker-compose.production.yml up -d car-1-pipeline car-2-pipeline

# 2. Monitor GPU (Linux specific, ignored on macOS for now)
if command -v nvidia-smi &> /dev/null; then
    echo "📊 Initial GPU State (NVIDIA):"
    nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
elif command -v rocm-smi &> /dev/null; then
    echo "📊 Initial GPU State (AMD):"
    rocm-smi --showuse --showmeminfo | grep "GPU"
fi

# 3. Launch Parallel Stress Tests via Docker Exec
# Using & to run in parallel
echo "⚡ Launching Car 1 Benchmark..."
docker exec rap_car_1_spine python3 tools/telemetry_gpu_stress_test.py --packets $PACKETS --chaos $CHAOS --output-suffix _car1 --diagnostic &
CAR1_PID=$!

echo "⚡ Launching Car 2 Benchmark..."
docker exec rap_car_2_spine python3 tools/telemetry_gpu_stress_test.py --packets $PACKETS --chaos $CHAOS --output-suffix _car2 --diagnostic &
CAR2_PID=$!

# 4. Wait for both to finish
echo "⏳ Monitoring parallel execution (PIDs: $CAR1_PID, $CAR2_PID)..."
wait $CAR1_PID
echo "✅ Car 1 Complete"
wait $CAR2_PID
echo "✅ Car 2 Complete"

# 5. Final Report Summary
echo "--------------------------------------------------------"
echo "🏆 TEAM TEST COMPLETE"
echo "--------------------------------------------------------"
echo "Check data/reports/ inside car-1-outputs and car-2-outputs volumes"
echo "or run docker-compose logs for terminal output."
echo "--------------------------------------------------------"
