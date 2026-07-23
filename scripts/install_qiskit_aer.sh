#!/bin/bash
set -euo pipefail

echo "=== Qiskit Aer GPU Installation Script ==="

# Check if qiskit-aer is already installed.
if python3 -c "import qiskit_aer" &> /dev/null; then
    echo "qiskit-aer is already installed."
    exit 0
fi

# Detect hardware environment.
if [[ "${IS_LUMI:-0}" == "1" ]] || command -v rocm-smi &> /dev/null; then
    echo "Detected ROCm environment (AMD GPU)."
    echo "Building qiskit-aer from source with ROCm/HIP support..."

    # Ensure build dependencies.
    python3 -m pip install cmake ninja scikit-build pybind11 --quiet
    python3 -c 'import pybind11; print("pybind11 include:", pybind11.get_include())'

    # Clone a stable release that still builds cleanly with the ROCm toolchain.
    git clone -b 0.15.1 https://github.com/Qiskit/qiskit-aer.git /tmp/qiskit-aer-src
    cd /tmp/qiskit-aer-src

    # Export build variables for ROCm.
    export QISKIT_AER_PACKAGE_NAME='qiskit-aer-gpu-rocm'
    export CXX=hipcc
    export CC=hipcc

    # Build the wheel.
    python3 setup.py bdist_wheel -- \
        -DAER_THRUST_BACKEND=ROCM \
        -DAER_ROCM_ARCH=gfx90a \
        -DCMAKE_CXX_COMPILER=hipcc \
        -DCMAKE_C_COMPILER=hipcc

    # Install the built wheel.
    python3 -m pip install dist/*.whl

    # Cleanup.
    rm -rf /tmp/qiskit-aer-src
    echo "Successfully installed qiskit-aer with ROCm support."

elif command -v nvidia-smi &> /dev/null; then
    echo "Detected CUDA environment (NVIDIA GPU)."
    echo "Installing pre-built qiskit-aer-gpu from PyPI..."
    python3 -m pip install qiskit-aer-gpu
    echo "Successfully installed qiskit-aer-gpu."

else
    echo "No compatible GPU detected (no ROCm or CUDA)."
    echo "Falling back to CPU-only qiskit-aer simulation."
    python3 -m pip install qiskit-aer
    echo "Successfully installed CPU qiskit-aer."
fi
