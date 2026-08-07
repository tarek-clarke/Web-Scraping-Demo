#!/bin/bash
set -euo pipefail

PROFILE="${LUMI_GPU_PROFILE:-single}"
case "$PROFILE" in
  single)
    LUMI_PARTITION="small-g"
    LUMI_GCDS=2
    LUMI_CPUS=16
    LUMI_MEM="128G"
    ;;
  full-node)
    LUMI_PARTITION="standard-g"
    LUMI_GCDS=8
    LUMI_CPUS=56
    LUMI_MEM="480G"
    ;;
  *)
    echo "ERROR: LUMI_GPU_PROFILE must be single or full-node" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$PROJECT_ROOT"

# Keep model and tokenizer caches on the project scratch filesystem.
CACHE_ROOT="${PROJECT_ROOT}/.cache"
export XDG_CACHE_HOME="$CACHE_ROOT"
export HF_HOME="${CACHE_ROOT}/huggingface"
export HF_DATASETS_CACHE="${HF_HOME}/datasets"
export TRANSFORMERS_CACHE="${HF_HOME}/transformers"
mkdir -p "$HF_DATASETS_CACHE" "$TRANSFORMERS_CACHE"

ORACLE="${ORACLE:-data/training/router_oracle_22500_v4_${PROFILE//-/_}.jsonl}"
MANIFEST="${ORACLE%.jsonl}.manifest.json"
DEPENDENCY_ARGS=()
if [ ! -s "$ORACLE" ] || ! grep -q '"status": "complete"' "$MANIFEST" 2>/dev/null; then
    ORACLE_JOB="$(sbatch --parsable \
        --partition="$LUMI_PARTITION" --gpus-per-node="$LUMI_GCDS" \
        --cpus-per-task="$LUMI_CPUS" --mem="$LUMI_MEM" \
        --export=ALL,PROJECT_ROOT="$PROJECT_ROOT",LUMI_GPU_PROFILE="$PROFILE",ORACLE="$ORACLE" \
        scripts/slurm/build_router_oracle.slurm)"
    DEPENDENCY_ARGS=(--dependency="afterok:${ORACLE_JOB}")
    echo "Oracle job:    $ORACLE_JOB (runs once; resumable)"
fi

TRAIN_JOB="$(sbatch --parsable "${DEPENDENCY_ARGS[@]}" \
    --partition="$LUMI_PARTITION" --gpus-per-node="$LUMI_GCDS" \
    --cpus-per-task="$LUMI_CPUS" --mem="$LUMI_MEM" \
    --export=ALL,PROJECT_ROOT="$PROJECT_ROOT",LUMI_GPU_PROFILE="$PROFILE",ORACLE="$ORACLE" \
    scripts/slurm/submit_train.slurm)"
SELECT_JOB="$(sbatch --parsable --dependency="afterok:${TRAIN_JOB}" \
    --partition="$LUMI_PARTITION" --gpus-per-node=1 \
    --cpus-per-task=8 --mem=64G \
    --export=ALL,PROJECT_ROOT="$PROJECT_ROOT",LUMI_GPU_PROFILE="$PROFILE",ORACLE="$ORACLE" \
    scripts/slurm/select_qpu_router.slurm)"

echo "LUMI profile:   $PROFILE ($LUMI_GCDS Slurm GPUs/GCDs)"
echo "Training array: $TRAIN_JOB (10 independent starts)"
echo "Selection job:  $SELECT_JOB (runs only after all starts succeed)"
echo "No physical-QPU job was submitted."
