#!/bin/bash
# Cloud Cohere full-corpus reconciliation baseline. The key must be supplied at submission
# time through COHERE_API_KEY; it is never written to the repository.
#SBATCH --job-name=cohere-full-22500
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=08:00:00
#SBATCH --output=cohere_full_stream_%j.out
#SBATCH --error=cohere_full_stream_%j.err

set -euo pipefail
PROJECT_ROOT="/scratch/project_465002996/clarketa/resilient-rap-tkde-aer-20260722"
cd "$PROJECT_ROOT"
: "${COHERE_API_KEY:?COHERE_API_KEY must be exported at sbatch submission time}"
export COHERE_API_KEY
source scripts/lumi_cache_env.sh
export SINGULARITYENV_COHERE_API_KEY="$COHERE_API_KEY"
export SINGULARITYENV_HF_HOME="$HF_HOME"
export SINGULARITYENV_TRANSFORMERS_CACHE="$TRANSFORMERS_CACHE"
module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings
LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
[ -r "$LUMI_SIF" ] || { echo "ERROR: LUMI container unavailable: $LUMI_SIF" >&2; exit 1; }
COHERE_OUTPUT_DIR="${COHERE_OUTPUT_DIR:-data/reports/cohere_full_stream_22500_20260810}"
COHERE_MAX_PACKETS_PER_API="${COHERE_MAX_PACKETS_PER_API:-2500}"
COHERE_DRIFT_RATE="${COHERE_DRIFT_RATE:-0.10}"
COHERE_METHODS="${COHERE_METHODS:-qwen json_manip schema_alter}"
COHERE_MAX_OUTPUT_TOKENS="${COHERE_MAX_OUTPUT_TOKENS:-256}"
: "${COHERE_MODEL:=command-a-plus-05-2026}"
mkdir -p "$COHERE_OUTPUT_DIR"
echo "Cohere chat model: $COHERE_MODEL"
echo "Output directory: $COHERE_OUTPUT_DIR"

singularity exec "$LUMI_SIF" python scripts/run_cohere_benchmark.py \
  --packets-file data/ingested/telemetry_clean_bench_22500.json \
  --run-number 1 \
  --drift-rate "$COHERE_DRIFT_RATE" \
  --methods $COHERE_METHODS \
  --max-packets-per-api "$COHERE_MAX_PACKETS_PER_API" \
  --repetitions 1 \
  --model "$COHERE_MODEL" \
  --max-output-tokens "$COHERE_MAX_OUTPUT_TOKENS" \
  --fail-on-api-error \
  --output-dir "$COHERE_OUTPUT_DIR"
