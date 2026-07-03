#!/bin/bash
#SBATCH --job-name=f1-sim-synthetic
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --time=00:10:00
#SBATCH --output=simulation_synthetic_%j.out
#SBATCH --error=simulation_synthetic_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Starting Full-Density Synthetic F1 Telemetry Simulation ==="
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

# Reset active telemetry file
rm -f data/ingested/telemetry_latest.json
touch data/ingested/telemetry_latest.json

# 1. Start the Live GPU Decoder in the background
echo "[Decoder] Starting live GPU decoder in background..."
python3 -u live_gpu_decoder.py --reconciler bert --chaos-rate 0.01 --poll-interval 1.0 --shadow-routing > simulation_decoder.log 2>&1 &
DECODER_PID=$!

# Wait for decoder to be fully initialized and tailing
echo "[Decoder] Waiting for reconciler model to load onto GPU..."
for i in {1..300}; do
    if grep -q "backlog" simulation_decoder.log 2>/dev/null; then
        echo "[Decoder] Reconciler is ready and tailing."
        break
    fi
    sleep 1
done

# Wait an additional 2 seconds to stabilize
sleep 2

# 2. Simulate the live stream using the synthetic generator
# Stream for 180 seconds (3 minutes) at 74 packets/sec (approx. 13,320 packets)
echo "[Ingestor] Starting synthetic generator..."
python3 scripts/generate_synthetic_race.py "data/ingested/telemetry_latest.json" 180

echo "[Ingestor] Finished streaming synthetic packets."

# Let the decoder poll and process the remaining lines
sleep 5

# 3. Gracefully stop the decoder
echo "[Decoder] Stopping decoder gracefully..."
kill -15 "$DECODER_PID"
wait "$DECODER_PID"

echo "=== Synthetic Simulation Complete ==="
echo "Decoder logs saved to: $PROJECT_ROOT/simulation_decoder.log"
echo "Check data/reports/live_f1/ for final results, manifest, and shadow logs."
echo "End time: $(date)"
