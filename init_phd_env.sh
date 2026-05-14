#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

detect_gpu_name() {
    if command -v nvidia-smi >/dev/null 2>&1; then
        nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1 | sed 's/^ *//;s/ *$//'
        return 0
    fi

    if command -v rocminfo >/dev/null 2>&1; then
        echo "AMD_ROCM"
        return 0
    fi

    if [[ "$(uname -s)" == "Darwin" ]]; then
        echo "Apple_Silicon"
        return 0
    fi

    echo "CPU"
}

map_gpu_to_cuda_arch() {
    local gpu_name="${1^^}"

    case "$gpu_name" in
        *"H100"*|*"H200"*)
            echo "9.0"
            ;;
        *"A100"*)
            echo "8.0"
            ;;
        *"L40"*|*"4090"*|*"RTX 4090"*|*"RTX4090"*|*"ADA"*)
            echo "8.9"
            ;;
        *"B200"*)
            echo "10.0"
            ;;
        *)
            echo ""
            ;;
    esac
}

detect_torch_cuda_arch_list() {
    if ! command -v nvidia-smi >/dev/null 2>&1; then
        return 0
    fi

    local archs=()
    local gpu_name
    while IFS= read -r gpu_name; do
        [[ -z "$gpu_name" ]] && continue
        local arch
        arch="$(map_gpu_to_cuda_arch "$gpu_name")"
        if [[ -n "$arch" ]] && [[ ! " ${archs[*]} " =~ " ${arch} " ]]; then
            archs+=("$arch")
        fi
    done < <(nvidia-smi --query-gpu=name --format=csv,noheader)

    if [[ ${#archs[@]} -gt 0 ]]; then
        local IFS=';'
        echo "${archs[*]}"
    fi
}

find_gcc_binary() {
    if command -v gcc >/dev/null 2>&1 && command -v g++ >/dev/null 2>&1; then
        local gcc_major
        gcc_major="$(gcc -dumpversion | cut -d. -f1)"
        if [[ "$gcc_major" =~ ^[0-9]+$ ]] && [[ "$gcc_major" -ge 9 ]]; then
            export CC="$(command -v gcc)"
            export CXX="$(command -v g++)"
            return 0
        fi
    fi

    if command -v module >/dev/null 2>&1; then
        local candidate
        for candidate in gcc/13 gcc/12 gcc/11 gcc/10 gcc/9; do
            if module load "$candidate" >/dev/null 2>&1; then
                if command -v gcc >/dev/null 2>&1 && command -v g++ >/dev/null 2>&1; then
                    local loaded_major
                    loaded_major="$(gcc -dumpversion | cut -d. -f1)"
                    if [[ "$loaded_major" =~ ^[0-9]+$ ]] && [[ "$loaded_major" -ge 9 ]]; then
                        export CC="$(command -v gcc)"
                        export CXX="$(command -v g++)"
                        export GCC_MODULE="${candidate}"
                        return 0
                    fi
                fi
            fi
        done
    fi

    return 1
}

export PROJECT_ROOT

GPU_NAME="$(detect_gpu_name)"
TORCH_CUDA_ARCH_LIST_VALUE="$(detect_torch_cuda_arch_list || true)"

if [[ -n "$TORCH_CUDA_ARCH_LIST_VALUE" ]]; then
    export RAP_BUILD_BACKEND="cuda"
    export TORCH_CUDA_ARCH_LIST="$TORCH_CUDA_ARCH_LIST_VALUE"
    echo "Detected NVIDIA GPU(s): $GPU_NAME"
    echo "TORCH_CUDA_ARCH_LIST=$TORCH_CUDA_ARCH_LIST"
elif [[ "$GPU_NAME" == "AMD_ROCM" ]]; then
    export RAP_BUILD_BACKEND="rocm"
    export FORCE_CPU=0
    export ROCM_PATH="${ROCM_PATH:-/opt/rocm}"
    echo "Detected ROCm-capable AMD environment."
elif [[ "$GPU_NAME" == "Apple_Silicon" ]]; then
    export RAP_BUILD_BACKEND="mps"
    export FORCE_CPU=0
    echo "Detected Apple Silicon environment; build will fall back to a CPU-compatible extension stub."
else
    export RAP_BUILD_BACKEND="cpu"
    echo "No GPU accelerator detected; building CPU-compatible extension stub."
fi

if find_gcc_binary; then
    echo "Using compiler: CC=$CC"
    echo "Using compiler: CXX=$CXX"
else
    echo "WARNING: No GCC 9+ compiler found via PATH or modules." >&2
    echo "Install/enable GCC 9+ before building the extension." >&2
fi

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo
    echo "Source this script to export the detected environment:"
    echo "  source ./init_phd_env.sh"
fi