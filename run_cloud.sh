#!/bin/bash
# High-Performance Cloud Benchmarking and Telemetry Pipeline Orchestrator
# Auto-installs, runs 100K-scale benchmark, profiles GPU, and auto-pushes back to GitHub

set -e # Exit immediately if a command exits with a non-zero status

# Prevent CUDA memory fragmentation and OOMs during concurrent model loading
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

echo "================================================================================"
echo " STARTING CLOUD BENCHMARK ORCHESTRATION"
echo "================================================================================"

# 1. Install dependencies and compile C++ acceleration
echo "[Cloud Orchestrator] Installing dependencies..."
python3 install_env.py

# 2. Run the dynamic matrix benchmark
echo "[Cloud Orchestrator] Executing benchmark matrix..."
python3 run_matrix_unified.py

# 3. Auto-detect GPU name
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -n 1 | sed 's/NVIDIA //g' | tr ' ' '_')
else
    GPU_NAME="CPU_Fallback"
fi

# Write hardware name to the Note file
echo "${GPU_NAME}" > Note

echo "================================================================================"
echo " UPLOADING DATASETS TO GITHUB"
echo "================================================================================"
# Configure Git identity locally inside the container to prevent author autodetect crashes
git config --local user.name "tarek-clarke"
git config --local user.email "tarek.clarke15@gmail.com"

# Force add results and Note file to bypass any cache blocks
git add Note
git add -f results/
git commit -m "data: upload benchmark telemetry results for ${GPU_NAME} ($(hostname))" || true

# Seamlessly pull and rebase concurrent results from other parallel VM runs
git pull --rebase origin main

git push origin main

echo "================================================================================"
echo " BENCHMARK & AUTO-PUSH COMPLETE!"
echo "================================================================================"
