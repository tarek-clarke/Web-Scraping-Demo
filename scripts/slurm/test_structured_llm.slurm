#!/bin/bash
#SBATCH --job-name=rap-llm-test
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --time=00:30:00
#SBATCH --output=structured_llm_%j.out
#SBATCH --error=structured_llm_%j.err

# A one-record acceptance test for an experimental local LLM reconciler.
# It cannot alter canonical router artifacts or submit to a physical QPU.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-${SLURM_SUBMIT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
METHOD="${LLM_METHOD:-phi_4_mini}"
cd "$PROJECT_ROOT"
source "$PROJECT_ROOT/scripts/lumi_cache_env.sh"

LUMI_SITE_PACKAGES="${RAP_LUMI_SITE_PACKAGES:-${PROJECT_ROOT}/.runtime/lumi/site-packages}"
test -d "$LUMI_SITE_PACKAGES" || { echo "Missing LUMI runtime; run bootstrap first." >&2; exit 1; }
export PYTHONPATH="$LUMI_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
export SINGULARITYENV_PYTHONPATH="$PYTHONPATH"
export HF_TORCH_DTYPE=bfloat16
export TOKENIZERS_PARALLELISM=false
export PYTORCH_ALLOC_CONF=expandable_segments:True

module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings
LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
test -r "$LUMI_SIF" || { echo "LUMI container is unavailable." >&2; exit 1; }

singularity run "$LUMI_SIF" python scripts/build_router_oracle.py \
  --packets-file data/ingested/telemetry_clean_bench_22500.json \
  --output "data/training/${METHOD}_preflight.jsonl" \
  --methods "$METHOD" \
  --max-packets-per-api 1 \
  --max-records 1 \
  --batch-size 1 \
  --preflight-only
