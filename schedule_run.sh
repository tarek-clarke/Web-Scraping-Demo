#!/bin/bash

# schedule_run.sh — Schedule F1 Live Ingestor and GPU Decoder.
# Usage: nohup ./schedule_run.sh 15:00 > schedule_run.log 2>&1 &

set -e

if [ -z "$1" ]; then
    echo "Error: Please specify a target start time in HH:MM format."
    echo "Usage: $0 <HH:MM>  (e.g., $0 15:00)"
    exit 1
fi

TARGET_TIME="$1"
PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-quantum"

# Prevent duplicate runs
LOCKFILE="/tmp/f1_schedule_run.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "ERROR: Another schedule_run.sh is already running (lockfile: $LOCKFILE)."; exit 1; }

# Validate that OpenF1 credentials are set
if [ -z "$OPENF1_EMAIL" ] || [ -z "$OPENF1_PASSWORD" ]; then
    echo "ERROR: OPENF1_EMAIL and OPENF1_PASSWORD must be exported before running this script."
    echo "  export OPENF1_EMAIL=\"your@email.com\""
    echo "  export OPENF1_PASSWORD=\"yourpassword\""
    exit 1
fi

echo "=== Scheduling Live F1 Telemetry Pipeline ==="
echo "Target Start Time: $TARGET_TIME"
echo ""

# Ensure we're in the project root for sbatch CWD inheritance
cd "$PROJECT_ROOT" || exit 1

# 1. Schedule the GPU Decoder job on SLURM
echo "[SLURM] Scheduling GPU Decoder to enter queue at $TARGET_TIME..."
SBATCH_OUT=$(sbatch --begin="$TARGET_TIME" "$PROJECT_ROOT/submit_live_decoder.slurm")
if [ $? -ne 0 ]; then
    echo "Error: Failed to schedule SLURM job."
    exit 1
fi
echo "Success: $SBATCH_OUT"
echo ""

# 2. Wait and start the Go Ingestor on the login node
TARGET_EPOCH=$(date -d "$TARGET_TIME" +%s)
CURRENT_EPOCH=$(date +%s)
SLEEP_SECONDS=$(( TARGET_EPOCH - CURRENT_EPOCH ))

if [ $SLEEP_SECONDS -lt 0 ]; then
    # If the time is for the next day, add 24 hours
    TARGET_EPOCH=$(( TARGET_EPOCH + 86400 ))
    SLEEP_SECONDS=$(( TARGET_EPOCH - CURRENT_EPOCH ))
fi

echo "[Ingestor] Calculating wait time..."
echo "Sleeping for $SLEEP_SECONDS seconds ($((SLEEP_SECONDS / 60)) minutes) until $TARGET_TIME..."
echo "You can close this connection/terminal after starting this script using 'nohup ./schedule_run.sh $TARGET_TIME &' if you want it to run fully detached."
echo "--------------------------------------------------"

sleep $SLEEP_SECONDS

echo "[$(date)] Time reached! Building and launching Go Ingestor..."
cd "$PROJECT_ROOT/go/ingestion" || exit 1

# Add Go to PATH (local workspace installation)
export PATH="/scratch/project_465002996/clarketa/go/bin:$PATH"

# Skip SpaceX client (polls 100 req/s, bloats telemetry file to 3GB+)
export SKIP_SPACEX=true

# Pre-compile ingestor binary (avoids 5-15s compilation delay at race start)
echo "[$(date)] Compiling Go ingestor..."
go build -o ./ingestor . 2>&1 || { echo "ERROR: Go build failed"; exit 1; }
echo "[$(date)] Build successful."

# Launch pre-compiled ingestor binary
/usr/bin/nohup ./ingestor > ingestion_live.log 2>&1 &
INGEST_PID=$!

# Write PID file so SLURM epilog can kill it when decoder finishes
echo "$INGEST_PID" > /tmp/f1_ingestor.pid

echo "[$(date)] Go Ingestor started successfully in background with PID $INGEST_PID!"
echo "Ingestor logging to $PROJECT_ROOT/go/ingestion/ingestion_live.log"
echo "GPU Decoder is now queued/running in SLURM."
echo "=== Scheduling Script Complete ==="
