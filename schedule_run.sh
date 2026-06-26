#!/bin/bash

# schedule_run.sh — Schedule F1 Live Ingestor and GPU Decoder for FP3.
# Usage: ./schedule_run.sh 15:00

if [ -z "$1" ]; then
    echo "Error: Please specify a target start time in HH:MM format."
    echo "Usage: $0 <HH:MM>  (e.g., $0 15:00)"
    exit 1
fi

TARGET_TIME="$1"
PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"

echo "=== Scheduling Live F1 Telemetry Pipeline ==="
echo "Target Start Time: $TARGET_TIME"
echo ""

# 1. Schedule the GPU Decoder job on SLURM
echo "[SLURM] Scheduling GPU Decoder to enter queue at $TARGET_TIME..."
# sbatch --begin accept HH:MM or HH:MM:SS format
SBATCH_OUT=$(sbatch --begin="$TARGET_TIME" "$PROJECT_ROOT/submit_live_decoder.slurm")
if [ $? -ne 0 ]; then
    echo "Error: Failed to schedule SLURM job."
    exit 1
fi
echo "Success: $SBATCH_OUT"
echo ""

# 2. Wait and start the Go Ingestor on the login node
# Works with GNU date (standard on LUMI/Linux)
TARGET_EPOCH=$(date -d "$TARGET_TIME" +%s)
CURRENT_EPOCH=$(date +%s)
SLEEP_SECONDS=$(( TARGET_EPOCH - CURRENT_EPOCH ))

if [ $SLEEP_SECONDS -le 0 ]; then
    # If the time is for the next day, add 24 hours (86400 seconds)
    TARGET_EPOCH=$(( TARGET_EPOCH + 86400 ))
    SLEEP_SECONDS=$(( TARGET_EPOCH - CURRENT_EPOCH ))
fi

echo "[Ingestor] Calculating wait time..."
echo "Sleeping for $SLEEP_SECONDS seconds ($((SLEEP_SECONDS / 60)) minutes) until $TARGET_TIME..."
echo "You can close this connection/terminal after starting this script using 'nohup ./schedule_run.sh $TARGET_TIME &' if you want it to run fully detached."
echo "--------------------------------------------------"

sleep $SLEEP_SECONDS

echo "[$(date)] Time reached! Launching Go Ingestor in the background..."
cd "$PROJECT_ROOT/go/ingestion" || exit 1

# Launch ingestor detached so it doesn't close when the terminal closes
nohup go run . > ingestion_live.log 2>&1 &
INGEST_PID=$!

echo "[$(date)] Go Ingestor started successfully in background with PID $INGEST_PID!"
echo "Ingestor logging to $PROJECT_ROOT/go/ingestion/ingestion_live.log"
echo "GPU Decoder is now queued/running in SLURM."
echo "=== Scheduling Script Complete ==="
