#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$PROJECT_ROOT"

ORACLE="${ORACLE:-data/training/router_oracle_22500_v2.jsonl}"
DEPENDENCY_ARGS=()
if [ ! -s "$ORACLE" ]; then
    ORACLE_JOB="$(sbatch --parsable --export=ALL,PROJECT_ROOT="$PROJECT_ROOT" \
        scripts/slurm/build_router_oracle.slurm)"
    DEPENDENCY_ARGS=(--dependency="afterok:${ORACLE_JOB}")
    echo "Oracle job:    $ORACLE_JOB (runs once; resumable)"
fi

TRAIN_JOB="$(sbatch --parsable "${DEPENDENCY_ARGS[@]}" \
    --export=ALL,PROJECT_ROOT="$PROJECT_ROOT" \
    scripts/slurm/submit_train.slurm)"
SELECT_JOB="$(sbatch --parsable --dependency="afterok:${TRAIN_JOB}" \
    --export=ALL,PROJECT_ROOT="$PROJECT_ROOT" \
    scripts/slurm/select_qpu_router.slurm)"

echo "Training array: $TRAIN_JOB (10 independent starts / up to 10 GPUs)"
echo "Selection job:  $SELECT_JOB (runs only after all starts succeed)"
echo "No physical-QPU job was submitted."
