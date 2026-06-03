#!/bin/bash

set -e

echo "=== Resilient RAP Framework - Hardware Detection ==="
echo ""

detect_nvidia() {
    if ! command -v nvidia-smi &> /dev/null; then
        return 1
    fi

    echo "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    DRIVER_MAJOR=$(echo $DRIVER_VERSION | cut -d. -f1)
    
    echo ""
    echo "Driver version: $DRIVER_VERSION"
    echo ""
    
    if [ $DRIVER_MAJOR -ge 570 ]; then
        CUDA_REC="13.3.0"
        UBUNTU_REC="26.04"
        echo "✓ Driver supports CUDA 13.3.0 (latest)"
    elif [ $DRIVER_MAJOR -ge 560 ]; then
        CUDA_REC="12.8.0"
        UBUNTU_REC="26.04"
        echo "✓ Driver supports CUDA 12.8.0 (latest stable)"
    elif [ $DRIVER_MAJOR -ge 550 ]; then
        CUDA_REC="12.4.0"
        UBUNTU_REC="24.04"
        echo "✓ Driver supports CUDA 12.4.0"
    elif [ $DRIVER_MAJOR -ge 525 ]; then
        CUDA_REC="12.4.0"
        UBUNTU_REC="24.04"
        echo "✓ Driver supports CUDA 12.4.0"
    else
        echo "⚠ Driver too old for CUDA 12.x. Update to 525.60+ or use CUDA 11.8"
        CUDA_REC="11.8.0"
        UBUNTU_REC="22.04"
    fi
    
    echo ""
    echo "Recommended build command:"
    echo "  CUDA_VERSION=$CUDA_REC UBUNTU_VERSION=$UBUNTU_REC docker-compose -f deploy/docker-compose.yml build rap-cuda"
    echo ""
    echo "Or with build script:"
    echo "  ./deploy/build-docker-matrix.sh cuda $CUDA_REC 7.2.4 $UBUNTU_REC"
    
    return 0
}

detect_amd() {
    if command -v rocm-smi &> /dev/null; then
        echo "AMD GPU detected (ROCm):"
        rocm-smi --showproductname
        echo ""
        ROCM_SMI_VERSION=$(rocm-smi --version 2>/dev/null | grep -oP 'ROCm SMI version: \K[0-9.]+' || echo "")
        if [ -n "$ROCM_SMI_VERSION" ]; then
            echo "ROCm SMI version: $ROCM_SMI_VERSION"
        fi
        echo ""
        echo "Recommended build command:"
        echo "  ROCM_VERSION=7.2.4 UBUNTU_VERSION=24.04 docker-compose -f deploy/docker-compose.yml build rap-rocm"
        echo ""
        echo "Or with build script:"
        echo "  ./deploy/build-docker-matrix.sh rocm 13.3.0 7.2.4 24.04"
        return 0
    fi

    if command -v lspci &> /dev/null; then
        if lspci | grep -i "AMD.*Radeon\|AMD.*Vega\|AMD.*Instinct" &> /dev/null; then
            echo "AMD GPU detected:"
            lspci | grep -i "AMD.*Radeon\|AMD.*Vega\|AMD.*Instinct"
            echo ""
            echo "Recommended build command:"
            echo "  ROCM_VERSION=7.2.4 UBUNTU_VERSION=24.04 docker-compose -f deploy/docker-compose.yml build rap-rocm"
            echo ""
            echo "Or with build script:"
            echo "  ./deploy/build-docker-matrix.sh rocm 13.3.0 7.2.4 24.04"
            return 0
        fi
    fi

    return 1
}

detect_apple_silicon() {
    if [ "$(uname)" != "Darwin" ]; then
        return 1
    fi

    CHIP=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "")
    if echo "$CHIP" | grep -qi "Apple"; then
        echo "Apple Silicon detected:"
        echo "  Chip: $CHIP"
        echo ""
        echo "Note: Apple Silicon uses Metal/MPS, not CUDA or ROCm."
        echo "Run natively instead of Docker:"
        echo ""
        echo "  ./deploy/macos/setup_m4.sh"
        echo "  python3 run_matrix.py --repetitions 3"
        return 0
    fi
    return 1
}

detect_cpu() {
    echo "No GPU detected. Using CPU-only mode."
    echo ""
    echo "CPU info:"
    if command -v lscpu &> /dev/null; then
        lscpu | grep "Model name" | head -1
    elif [ "$(uname)" = "Darwin" ]; then
        echo "  $(sysctl -n machdep.cpu.brand_string 2>/dev/null)"
    fi
    echo ""
    echo "Recommended build command:"
    echo "  UBUNTU_VERSION=26.04 docker-compose -f deploy/docker-compose.yml build rap-cpu"
    echo ""
    echo "Or with build script:"
    echo "  ./deploy/build-docker-matrix.sh cpu 13.3.0 7.2.4 26.04"
}

echo "Checking for GPUs..."
echo ""

NVIDIA_FOUND=0
AMD_FOUND=0
APPLE_FOUND=0

if detect_nvidia; then
    NVIDIA_FOUND=1
fi

echo ""

if detect_amd; then
    AMD_FOUND=1
fi

echo ""

if detect_apple_silicon; then
    APPLE_FOUND=1
fi

if [ $NVIDIA_FOUND -eq 0 ] && [ $AMD_FOUND -eq 0 ] && [ $APPLE_FOUND -eq 0 ]; then
    detect_cpu
fi

echo ""
echo "=== Detection Complete ==="
echo ""
echo "Next steps:"
echo "1. Download models: ./models/download_from_r2.sh"
echo "2. Run ingestion: cd go/ingestion && go run main.go && cd ../.."
echo "3. Build image with recommended versions above"
echo "4. Run matrix: docker-compose -f deploy/docker-compose.yml up rap-cuda (or rap-rocm/rap-cpu)"
