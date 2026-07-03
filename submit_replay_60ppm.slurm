#!/bin/bash
#SBATCH --job-name=f1-replay-60ppm
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --time=00:45:00
#SBATCH --output=replay_60ppm_%j.out
#SBATCH --error=replay_60ppm_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Replaying Last Week's Race at 60 Packets/Minute ==="
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

# Target last week's telemetry file
MOCK_SOURCE="data/ingested/telemetry_20260628_175112.json"

if [ ! -f "$MOCK_SOURCE" ]; then
    echo "ERROR: Last week's telemetry file $MOCK_SOURCE not found."
    exit 1
fi

TOTAL_LINES=$(wc -l < "$MOCK_SOURCE")
echo "Telemetry File: $MOCK_SOURCE ($TOTAL_LINES packets)"
echo "Target Rate: 60 packets/minute (1.0s interval)"
echo "Estimated Duration: ~34 minutes"

# Reset active telemetry file
rm -f data/ingested/telemetry_replay_60ppm.json
touch data/ingested/telemetry_replay_60ppm.json

# 1. Start the Live GPU Decoder in the background
echo "[Decoder] Starting live GPU decoder in background..."
python3 -u live_gpu_decoder.py --reconciler bert --chaos-rate 0.01 --poll-interval 1.0 --shadow-routing --telemetry-file data/ingested/telemetry_replay_60ppm.json > simulation_decoder_replay.log 2>&1 &
DECODER_PID=$!

# Wait for decoder to be fully initialized and tailing
echo "[Decoder] Waiting for reconciler model to load onto GPU..."
for i in {1..300}; do
    if grep -q "backlog" simulation_decoder_replay.log 2>/dev/null; then
        echo "[Decoder] Reconciler is ready and tailing."
        break
    fi
    sleep 1
done

# Wait an additional 2 seconds to stabilize
sleep 2

# 2. Simulate the live stream by writing lines with a 1.0 second delay (60 PPM)
echo "[Ingestor] Starting live stream simulation at 60 PPM..."
PACKET_COUNT=0
cat "$MOCK_SOURCE" | while read -r line; do
    echo "$line" >> data/ingested/telemetry_replay_60ppm.json
    PACKET_COUNT=$((PACKET_COUNT + 1))
    
    # Print progress every 60 packets (approx. every minute)
    if [ $((PACKET_COUNT % 60)) -eq 0 ]; then
        echo "[Ingestor] Sent $PACKET_COUNT / $TOTAL_LINES packets..."
    fi
    
    sleep 1.0
done

echo "[Ingestor] Finished feeding all packets."

# Let the decoder poll and process the remaining lines
sleep 5

# 3. Gracefully stop the decoder
echo "[Decoder] Stopping decoder gracefully..."
kill -15 "$DECODER_PID"
wait "$DECODER_PID"

echo "=== Replay 60 PPM Complete ==="
echo "Decoder logs saved to: $PROJECT_ROOT/simulation_decoder_replay.log"
echo "Check data/reports/live_f1/ for final results and full shadow logs."
echo "End time: $(date)"
