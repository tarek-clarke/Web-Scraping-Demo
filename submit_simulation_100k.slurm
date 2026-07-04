#!/bin/bash
#SBATCH --job-name=f1-sim-100k
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --time=00:15:00
#SBATCH --output=simulation_100k_%j.out
#SBATCH --error=simulation_100k_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Starting 100k Packets F1 Telemetry Simulation ==="
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
rm -f data/ingested/telemetry_100k.json
touch data/ingested/telemetry_100k.json

# 1. Start the Live GPU Decoder in the background
echo "[Decoder] Starting live GPU decoder in background..."
# We set poll-interval to 1.0s and batch-size to 128 for high throughput, chaos rate at 0.01
python3 -u live_gpu_decoder.py --reconciler bert --chaos-rate 0.01 --poll-interval 1.0 --batch-size 128 --shadow-routing --telemetry-file data/ingested/telemetry_100k.json > simulation_decoder_100k.log 2>&1 &
DECODER_PID=$!

# Wait for decoder to be fully initialized and tailing
echo "[Decoder] Waiting for reconciler model to load onto GPU..."
for i in {1..300}; do
    if grep -q "backlog" simulation_decoder_100k.log 2>/dev/null; then
        echo "[Decoder] Reconciler is ready and tailing."
        break
    fi
    sleep 1
done

# Wait an additional 2 seconds to stabilize
sleep 2

# 2. Simulate the live stream using the blaster script
echo "[Ingestor] Starting 100k packet blaster..."
python3 scripts/generate_100k_blast.py "data/ingested/telemetry_100k.json"

echo "[Ingestor] Finished streaming 100k packets."

# Let the decoder finish polling and processing the remaining lines
echo "[Decoder] Waiting 15 seconds for decoder to drain remaining buffer..."
sleep 15

# 3. Gracefully stop the decoder
echo "[Decoder] Stopping decoder gracefully..."
kill -15 "$DECODER_PID"
wait "$DECODER_PID"

echo "=== 100k Simulation Complete ==="
echo "Decoder logs saved to: $PROJECT_ROOT/simulation_decoder_100k.log"
echo "Check data/reports/live_f1/ for final results, manifest, and shadow logs."
echo "End time: $(date)"
