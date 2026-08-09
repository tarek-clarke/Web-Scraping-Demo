#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
PYTHON_BIN="${RAP_PYTHON_BIN:-python3}"
CACHE_ROOT="${RAP_CACHE_ROOT:-$PROJECT_ROOT/.cache}"
export XDG_CACHE_HOME="$CACHE_ROOT"
export HF_HOME="${HF_HOME:-$CACHE_ROOT/huggingface}"
export HF_DATASETS_CACHE="${HF_DATASETS_CACHE:-$HF_HOME/datasets}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
mkdir -p "$HF_DATASETS_CACHE" "$TRANSFORMERS_CACHE"

if [ -z "${COHERE_API_KEY:-}" ]; then
    echo "ERROR: COHERE_API_KEY must be exported in this shell." >&2
    exit 1
fi
export RAP_REQUIRE_GPU_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false

readarray -t GPU_INFO < <("$PYTHON_BIN" - <<'PY'
import re, torch
if not torch.cuda.is_available() or torch.version.hip:
    raise SystemExit("ERROR: this launcher requires NVIDIA CUDA; use the LUMI Slurm launcher for ROCm")
name = torch.cuda.get_device_name(0)
print(torch.cuda.device_count())
print(re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"))
PY
)
GPU_COUNT="${GPU_INFO[0]}"
HARDWARE_TAG="${RAP_HARDWARE_TAG:-${GPU_INFO[1]}}"
WORKERS="${RAP_GPU_WORKERS:-$GPU_COUNT}"
if [ "$WORKERS" -lt 1 ] || [ "$WORKERS" -gt "$GPU_COUNT" ]; then
    echo "ERROR: RAP_GPU_WORKERS must be between 1 and $GPU_COUNT." >&2
    exit 1
fi

# Preserve the provider/scheduler allocation instead of assuming that visible
# logical device N is host physical device N. Tokens may be indices or UUIDs.
GPU_TOKENS=()
if [ -n "${CUDA_VISIBLE_DEVICES:-}" ]; then
    IFS=',' read -r -a GPU_TOKENS <<< "$CUDA_VISIBLE_DEVICES"
else
    for ((rank=0; rank<GPU_COUNT; rank++)); do
        GPU_TOKENS+=("$rank")
    done
fi
if [ "${#GPU_TOKENS[@]}" -ne "$GPU_COUNT" ]; then
    echo "ERROR: CUDA_VISIBLE_DEVICES describes ${#GPU_TOKENS[@]} token(s), but PyTorch sees $GPU_COUNT GPU(s)." >&2
    exit 1
fi

ORACLE="${ORACLE:-data/training/router_oracle_22500_v6_${HARDWARE_TAG}.jsonl}"
ORACLE_STEM="${ORACLE%.jsonl}"
CANDIDATES="data/training/qpu_router_multistart_v6_${HARDWARE_TAG}"
MODEL="configs/quantum_router_v6_${HARDWARE_TAG}.json"
mkdir -p data/training "$CANDIDATES" configs
ENERGY_SUMMARIES=()

"$PYTHON_BIN" scripts/preflight_accelerator.py \
    --expected-devices "$GPU_COUNT" --profile full --require-aer --require-router-qnn \
    --require-cohere \
    --require-power-telemetry \
    --json-output "data/training/preflight_${HARDWARE_TAG}.json"

MANIFEST="${ORACLE%.jsonl}.manifest.json"
if [ ! -s "$ORACLE" ] || ! grep -q '"status": "complete"' "$MANIFEST" 2>/dev/null; then
    PIDS=()
    SHARDS=()
    for ((rank=0; rank<WORKERS; rank++)); do
        SHARD="${ORACLE_STEM}.part_${rank}.jsonl"
        SHARDS+=("$SHARD")
        (
            export CUDA_VISIBLE_DEVICES="${GPU_TOKENS[$rank]}"
            export RAP_CPU_WORKERS="${RAP_CPU_WORKERS_PER_GPU:-4}"
            "$PYTHON_BIN" scripts/preflight_accelerator.py \
                --expected-devices 1 --profile oracle --require-cohere \
                --json-output "${ORACLE_STEM}.part_${rank}.preflight.json"
            "$PYTHON_BIN" scripts/run_with_energy.py \
                --csv "${SHARD%.jsonl}.energy.csv" \
                --summary "${SHARD%.jsonl}.energy_summary.json" \
                --label "oracle-${HARDWARE_TAG}-shard-${rank}" -- \
                "$PYTHON_BIN" -u scripts/build_router_oracle.py \
                    --packets-file data/ingested/telemetry_clean_bench_22500.json \
                    --output "$SHARD" --max-packets-per-api 2500 \
                    --chunk-size 31500 --batch-size 64 --accuracy-sla 0.95 \
                    --num-shards "$WORKERS" --shard-index "$rank" --resume
        ) >"oracle_${HARDWARE_TAG}_part_${rank}.out" \
          2>"oracle_${HARDWARE_TAG}_part_${rank}.err" &
        PIDS+=("$!")
    done
    FAILED=0
    for pid in "${PIDS[@]}"; do
        wait "$pid" || FAILED=1
    done
    if [ "$FAILED" -ne 0 ]; then
        echo "ERROR: at least one NVIDIA oracle shard failed; merge and training were not started." >&2
        exit 1
    fi
    "$PYTHON_BIN" scripts/merge_router_oracle_shards.py \
        --output "$ORACLE" --expected-records 31500 --shards "${SHARDS[@]}"
fi
for ((rank=0; rank<WORKERS; rank++)); do
    SUMMARY_PATH="${ORACLE_STEM}.part_${rank}.energy_summary.json"
    if [ -s "$SUMMARY_PATH" ]; then
        ENERGY_SUMMARIES+=("$SUMMARY_PATH")
    fi
done

if [ "${RAP_SKIP_TRAINING:-0}" = "1" ]; then
    if [ "${#ENERGY_SUMMARIES[@]}" -gt 0 ]; then
        "$PYTHON_BIN" scripts/summarize_energy.py \
            --output-prefix "data/training/energy_summary_${HARDWARE_TAG}_oracle" \
            --inputs "${ENERGY_SUMMARIES[@]}"
    fi
    echo "Oracle complete; RAP_SKIP_TRAINING=1, so VQC training was skipped."
    exit 0
fi

for ((batch_start=0; batch_start<10; batch_start+=WORKERS)); do
    PIDS=()
    for ((rank=0; rank<WORKERS && batch_start+rank<10; rank++)); do
        START_INDEX="$((batch_start + rank))"
        (
            export CUDA_VISIBLE_DEVICES="${GPU_TOKENS[$rank]}"
            "$PYTHON_BIN" scripts/preflight_accelerator.py \
                --expected-devices 1 --profile training --require-aer \
                --require-router-qnn \
                --json-output "data/training/preflight_train_${HARDWARE_TAG}_${START_INDEX}.json"
            "$PYTHON_BIN" scripts/run_with_energy.py \
                --csv "data/training/energy_train_${HARDWARE_TAG}_${START_INDEX}.csv" \
                --summary "data/training/energy_train_${HARDWARE_TAG}_${START_INDEX}.json" \
                --label "vqc-train-${HARDWARE_TAG}-${START_INDEX}" -- \
                "$PYTHON_BIN" -u scripts/train_qpu_router.py train \
                    --oracle "$ORACLE" --output-dir "$CANDIDATES" \
                    --start-index "$START_INDEX" --backend aer_gpu \
                    --training-shots 512 --maxiter "${RAP_TRAIN_MAXITER:-200}"
        ) >"vqc_train_${HARDWARE_TAG}_${START_INDEX}.out" \
          2>"vqc_train_${HARDWARE_TAG}_${START_INDEX}.err" &
        PIDS+=("$!")
    done
    FAILED=0
    for pid in "${PIDS[@]}"; do
        wait "$pid" || FAILED=1
    done
    if [ "$FAILED" -ne 0 ]; then
        echo "ERROR: a VQC training start failed; model selection was not run." >&2
        exit 1
    fi
done
for ((start_index=0; start_index<10; start_index++)); do
    ENERGY_SUMMARIES+=("data/training/energy_train_${HARDWARE_TAG}_${start_index}.json")
done

CUDA_VISIBLE_DEVICES="${GPU_TOKENS[0]}" "$PYTHON_BIN" scripts/preflight_accelerator.py \
    --expected-devices 1 --profile training --require-aer --require-router-qnn \
    --json-output "data/training/preflight_select_${HARDWARE_TAG}.json"
CUDA_VISIBLE_DEVICES="${GPU_TOKENS[0]}" "$PYTHON_BIN" scripts/run_with_energy.py \
    --csv "data/training/energy_select_${HARDWARE_TAG}.csv" \
    --summary "data/training/energy_select_${HARDWARE_TAG}.json" \
    --label "vqc-select-${HARDWARE_TAG}" -- \
    "$PYTHON_BIN" -u scripts/train_qpu_router.py select \
        --oracle "$ORACLE" --candidates-dir "$CANDIDATES" \
        --model-output "$MODEL" --expected-starts 10 --backend aer_gpu \
        --evaluation-shots 2048 --min-macro-f1 0.70 --min-balanced-accuracy 0.70
ENERGY_SUMMARIES+=("data/training/energy_select_${HARDWARE_TAG}.json")
"$PYTHON_BIN" scripts/summarize_energy.py \
    --output-prefix "data/training/energy_summary_${HARDWARE_TAG}" \
    --inputs "${ENERGY_SUMMARIES[@]}"

echo "Accelerator pipeline complete: $HARDWARE_TAG"
echo "Oracle: $ORACLE"
echo "Selected model: $MODEL"
