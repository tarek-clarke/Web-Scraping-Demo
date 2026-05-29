#!/bin/bash
# ==============================================================================
# IEEE T-DKE Resilient Semantic Reconciliation under Drift Pipeline Runner
# ==============================================================================
# This script automates:
#   1. Syncing the latest codebase via Git Pull.
#   2. Verifying or procedurally generating the evaluation chaos dataset.
#   3. Executing the scientific semantic benchmark under strict offline parameters.
#   4. Compiling post-hoc analytical metrics and auto-updating README.md.
# ==============================================================================
set -e

# Determine the script directory to run relatively from root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "================================================================================"
echo " 🔄 STARTING PIPELINE SYNC & RUN (IEEE T-DKE PRIMARY PATH)"
echo "================================================================================"

# 1. Pull latest code from remote
echo "[*] Syncing workspace with origin/main..."
if command -v git &> /dev/null; then
    git pull origin main
else
    echo "[!] Warning: git command not found; skipping repository sync."
fi

# 2. Check or generate the static chaos dataset
DATASET_PATH="chaos_generator/datasets/chaos_dataset.json"
if [ ! -f "$DATASET_PATH" ]; then
    echo "[!] Warning: Static chaos dataset not found at $DATASET_PATH."
    echo "[*] Procedurally generating chaos dataset..."
    python chaos_generator/generate_chaos_dataset.py \
      --output-dir chaos_generator/datasets \
      --runs-per-config 5 \
      --strategies json schema
fi

# 3. Run semantic benchmark
echo "[*] Executing scientific semantic translation benchmark..."
python semantic_benchmark/run_semantic_benchmark.py \
  --dataset-path "$DATASET_PATH" \
  --require-local-models True \
  --strict-mode \
  --verbose

# 4. Auto-update README tables with latest findings
echo "[*] Formatting experimental outcomes and updating tables..."
python scripts/update_readme_tables.py

echo "================================================================================"
echo " [✓] PIPELINE SYNC, BENCHMARK EXECUTION, & README UPDATE COMPLETE!"
echo "================================================================================"
