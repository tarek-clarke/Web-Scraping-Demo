#!/bin/bash
# Keep all user-writable runtime state on the project scratch filesystem.
# Source this after PROJECT_ROOT has been resolved.
set -euo pipefail

: "${PROJECT_ROOT:?PROJECT_ROOT must be set before sourcing lumi_cache_env.sh}"

RAP_CACHE_ROOT="${RAP_CACHE_ROOT:-$PROJECT_ROOT/.cache}"
RAP_RUNTIME_HOME="${RAP_RUNTIME_HOME:-$PROJECT_ROOT/.runtime/home}"

export HOME="$RAP_RUNTIME_HOME"
export XDG_CACHE_HOME="$RAP_CACHE_ROOT"
export PIP_CACHE_DIR="$RAP_CACHE_ROOT/pip"
export HF_HOME="$RAP_CACHE_ROOT/huggingface"
export HF_DATASETS_CACHE="$HF_HOME/datasets"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
export TORCH_HOME="$RAP_CACHE_ROOT/torch"
export TORCH_EXTENSIONS_DIR="$RAP_CACHE_ROOT/torch_extensions"
export TRITON_CACHE_DIR="$RAP_CACHE_ROOT/triton"
export AMD_COMGR_CACHE="$RAP_CACHE_ROOT/amd-comgr"
export CCACHE_DIR="$RAP_CACHE_ROOT/ccache"
export MPLCONFIGDIR="$RAP_CACHE_ROOT/matplotlib"
export NUMBA_CACHE_DIR="$RAP_CACHE_ROOT/numba"
export JUPYTER_CONFIG_DIR="$RAP_CACHE_ROOT/jupyter"
export TMPDIR="$RAP_CACHE_ROOT/tmp"
export PYTHONNOUSERSITE=1

mkdir -p \
    "$RAP_RUNTIME_HOME" "$PIP_CACHE_DIR" "$HF_DATASETS_CACHE" \
    "$TRANSFORMERS_CACHE" "$TORCH_HOME" "$TORCH_EXTENSIONS_DIR" \
    "$TRITON_CACHE_DIR" "$AMD_COMGR_CACHE" "$CCACHE_DIR" \
    "$MPLCONFIGDIR" "$NUMBA_CACHE_DIR" "$JUPYTER_CONFIG_DIR" "$TMPDIR"

# Singularity imports variables prefixed with SINGULARITYENV_ into the
# container. Explicitly propagate every cache location and HOME override.
for name in \
    HOME XDG_CACHE_HOME PIP_CACHE_DIR HF_HOME HF_DATASETS_CACHE \
    TRANSFORMERS_CACHE TORCH_HOME TORCH_EXTENSIONS_DIR TRITON_CACHE_DIR \
    AMD_COMGR_CACHE CCACHE_DIR MPLCONFIGDIR NUMBA_CACHE_DIR \
    JUPYTER_CONFIG_DIR TMPDIR PYTHONNOUSERSITE; do
    export "SINGULARITYENV_${name}=${!name}"
done
