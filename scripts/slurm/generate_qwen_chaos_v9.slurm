#!/bin/bash
#SBATCH --job-name=qwen-chaos-v9
#SBATCH --account=project_465002996
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
#SBATCH --output=qwen_chaos_v9_%j.out
#SBATCH --error=qwen_chaos_v9_%j.err

set -euo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-${SLURM_SUBMIT_DIR:?submit from the repository root}}"
cd "$PROJECT_ROOT"
source "$PROJECT_ROOT/scripts/lumi_cache_env.sh"

module purge
module use /appl/local/laifs/modules
module load lumi-aif-singularity-bindings
LUMI_SIF="${LUMI_SIF:-/appl/local/laifs/containers/lumi-multitorch-u24r70f21m50t210-20260731_122833/lumi-multitorch-full-u24r70f21m50t210-20260731_122833.sif}"
[ -r "$LUMI_SIF" ] || { echo "ERROR: unreadable LUMI container: $LUMI_SIF" >&2; exit 1; }

PACKETS="${RAP_REAL_SNAPSHOT:-data/ingested/telemetry_real_api_22500_v1.json}"
OUTPUT="${RAP_QWEN_CHAOS_FILE:-data/training/qwen_model_chaos_22500_v1.jsonl}"
[ -f "$PACKETS" ] || { echo "ERROR: missing real API snapshot: $PACKETS" >&2; exit 1; }

singularity exec "$LUMI_SIF" python - <<'PY'
import torch
if not torch.cuda.is_available() or not torch.version.hip:
    raise SystemExit("ERROR: ROCm GPU unavailable; Qwen CPU fallback is forbidden")
print("Qwen chaos device:", torch.cuda.get_device_name(0), flush=True)
PY

singularity exec "$LUMI_SIF" python scripts/build_qwen_chaos_snapshot.py \
  --packets "$PACKETS" \
  --output "$OUTPUT" \
  --batch-size "${RAP_QWEN_CHAOS_BATCH_SIZE:-16}" \
  --overwrite
