#!/bin/bash
#SBATCH --job-name=f1-sim-test
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --time=00:10:00
#SBATCH --output=simulation_%j.out
#SBATCH --error=simulation_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Starting Live F1 Ingestion & Decoding Simulation ==="
echo "Node: $SLURM_NODENAME"
echo "Allocated GPUs: $SLURM_GPUS_ON_NODE"
echo "Start time: $(date)"

# Load modules
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate venv
source "$PROJECT_ROOT/.venv-lumi/bin/activate"

# Environment variables
export IS_LUMI=1
export HF_HOME=/scratch/project_465002996/clarketa/hf_cache
export CHAOS_DEVICE=cuda:0

# Find the most recent historical telemetry file to use as stream source
MOCK_SOURCE=$(ls -t data/ingested/telemetry_*.json 2>/dev/null | grep -v "latest" | head -n 1)

if [ -z "$MOCK_SOURCE" ]; then
    echo "ERROR: No historical telemetry files found in data/ingested/ to run the simulation."
    exit 1
fi

echo "Selected Mock Stream Source: $MOCK_SOURCE"

# Reset telemetry files
rm -f data/ingested/telemetry_latest.json
touch data/ingested/telemetry_latest.json

# 1. Start the Live GPU Decoder in the background
echo "[Decoder] Starting live GPU decoder in background..."
python3 -u live_gpu_decoder.py --reconciler bert --chaos-rate 0.10 --poll-interval 1.0 --shadow-routing > simulation_decoder.log 2>&1 &
DECODER_PID=$!

# Wait for decoder to be fully initialized and ready (polling log file)
echo "[Decoder] Waiting for reconciler model to load onto GPU..."
for i in {1..300}; do
    if grep -q "Reconciler ready" simulation_decoder.log 2>/dev/null; then
        echo "[Decoder] Reconciler is ready."
        break
    fi
    sleep 1
done

# Wait an additional 2 seconds to ensure the symlink target is stable
sleep 2

# 2. Simulate the live stream by writing lines with a delay
echo "[Ingestor] Simulating live stream by feeding packets..."
# Stream up to 1,500 packets with a 0.03-second delay (approx. 45s total streaming runtime)
head -n 1500 "$MOCK_SOURCE" | while read -r line; do
    echo "$line" >> data/ingested/telemetry_latest.json
    sleep 0.03
done

echo "[Ingestor] Finished feeding simulation packets."

# Let the decoder poll and process the remaining lines
sleep 5

# 3. Gracefully stop the decoder using SIGTERM to trigger manifest & shadow log write
echo "[Decoder] Stopping decoder gracefully..."
kill -15 "$DECODER_PID"
wait "$DECODER_PID"

echo "=== Simulation Complete ==="
echo "Decoder logs saved to: $PROJECT_ROOT/simulation_decoder.log"
echo "Check data/reports/live_f1/ for new live_results_*.csv, manifest_*.json, and shadow_log_*.json files."
echo "End time: $(date)"
