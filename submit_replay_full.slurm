#!/bin/bash
#SBATCH --job-name=f1-replay-full
#SBATCH --account=project_465002996
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=7
#SBATCH --time=00:15:00
#SBATCH --output=replay_full_%j.out
#SBATCH --error=replay_full_%j.err

PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"
cd "$PROJECT_ROOT" || exit 1

echo "=== Replaying Last Week's Full Race Telemetry ==="
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

# Target the full telemetry file from last week's race
MOCK_SOURCE="data/ingested/telemetry_20260628_175112.json"

if [ ! -f "$MOCK_SOURCE" ]; then
    echo "ERROR: Last week's telemetry file $MOCK_SOURCE not found."
    exit 1
fi

TOTAL_LINES=$(wc -l < "$MOCK_SOURCE")
echo "Telemetry File: $MOCK_SOURCE ($TOTAL_LINES packets)"

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

# 2. Feed the entire file at once (instant replay)
echo "[Ingestor] Feeding all $TOTAL_LINES packets to the decoder..."
cat "$MOCK_SOURCE" >> data/ingested/telemetry_latest.json

# 3. Monitor processing progress until all packets are handled
echo "[Decoder] Processing packets..."
EXPECTED_MATCH="Total: $TOTAL_LINES"
for i in {1..120}; do
    # Check if the log shows that all packets have been processed
    if grep -q "Total: $TOTAL_LINES" simulation_decoder.log 2>/dev/null; then
        echo "[Decoder] All packets processed successfully."
        break
    fi
    # Print the last status line to show progress in stdout
    grep -o "Processed .* Total: [0-9]*" simulation_decoder.log 2>/dev/null | tail -n 1
    sleep 2
done

# Let the decoder finish writing buffers
sleep 5

# 4. Gracefully stop the decoder
echo "[Decoder] Stopping decoder gracefully..."
kill -15 "$DECODER_PID"
wait "$DECODER_PID"

echo "=== Replay Complete ==="
echo "Decoder logs saved to: $PROJECT_ROOT/simulation_decoder.log"
echo "Check data/reports/live_f1/ for final results and full shadow logs."
echo "End time: $(date)"
