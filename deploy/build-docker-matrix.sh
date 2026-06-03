#!/bin/bash

set -e

echo "=== Resilient RAP Framework - Docker Build Matrix ==="

HARDWARE_TYPE=${1:-cuda}
CUDA_VERSION=${2:-12.3.0}
ROCM_VERSION=${3:-6.0}
UBUNTU_VERSION=${4:-22.04}
PYTORCH_VERSION=${5:-2.1.1}

echo "Hardware: $HARDWARE_TYPE"
echo "CUDA Version: $CUDA_VERSION"
echo "ROCm Version: $ROCM_VERSION"
echo "Ubuntu Version: $UBUNTU_VERSION"
echo "PyTorch Version: $PYTORCH_VERSION"
echo ""

case $HARDWARE_TYPE in
    cuda)
        echo "Building CUDA image..."
        docker build \
            --build-arg CUDA_VERSION=$CUDA_VERSION \
            --build-arg UBUNTU_VERSION=$UBUNTU_VERSION \
            -f deploy/docker/Dockerfile.cuda \
            -t resilient-rap:cuda-${CUDA_VERSION}-ubuntu${UBUNTU_VERSION} \
            .
        echo "✓ Built: resilient-rap:cuda-${CUDA_VERSION}-ubuntu${UBUNTU_VERSION}"
        ;;
    
    rocm)
        echo "Building ROCm image..."
        docker build \
            --build-arg ROCM_VERSION=$ROCM_VERSION \
            --build-arg UBUNTU_VERSION=$UBUNTU_VERSION \
            --build-arg PYTORCH_VERSION=$PYTORCH_VERSION \
            -f deploy/docker/Dockerfile.rocm \
            -t resilient-rap:rocm-${ROCM_VERSION}-ubuntu${UBUNTU_VERSION} \
            .
        echo "✓ Built: resilient-rap:rocm-${ROCM_VERSION}-ubuntu${UBUNTU_VERSION}"
        ;;
    
    cpu)
        echo "Building CPU image..."
        docker build \
            --build-arg UBUNTU_VERSION=$UBUNTU_VERSION \
            -f deploy/docker/Dockerfile.cpu \
            -t resilient-rap:cpu-ubuntu${UBUNTU_VERSION} \
            .
        echo "✓ Built: resilient-rap:cpu-ubuntu${UBUNTU_VERSION}"
        ;;
    
    all)
        echo "Building all variants..."
        
        echo ""
        echo "=== CUDA Variants ==="
        for cuda_ver in 11.8.0 12.1.0 12.3.0 12.4.0; do
            for ubuntu_ver in 22.04 24.04; do
                echo "Building CUDA $cuda_ver + Ubuntu $ubuntu_ver..."
                docker build \
                    --build-arg CUDA_VERSION=$cuda_ver \
                    --build-arg UBUNTU_VERSION=$ubuntu_ver \
                    -f deploy/docker/Dockerfile.cuda \
                    -t resilient-rap:cuda-${cuda_ver}-ubuntu${ubuntu_ver} \
                    . || echo "⚠ Failed: cuda-${cuda_ver}-ubuntu${ubuntu_ver}"
            done
        done
        
        echo ""
        echo "=== ROCm Variants ==="
        for rocm_ver in 6.0 6.1 6.2; do
            for ubuntu_ver in 22.04; do
                echo "Building ROCm $rocm_ver + Ubuntu $ubuntu_ver..."
                docker build \
                    --build-arg ROCM_VERSION=$rocm_ver \
                    --build-arg UBUNTU_VERSION=$ubuntu_ver \
                    --build-arg PYTORCH_VERSION=2.1.1 \
                    -f deploy/docker/Dockerfile.rocm \
                    -t resilient-rap:rocm-${rocm_ver}-ubuntu${ubuntu_ver} \
                    . || echo "⚠ Failed: rocm-${rocm_ver}-ubuntu${ubuntu_ver}"
            done
        done
        
        echo ""
        echo "=== CPU Variants ==="
        for ubuntu_ver in 22.04 24.04; do
            echo "Building CPU + Ubuntu $ubuntu_ver..."
            docker build \
                --build-arg UBUNTU_VERSION=$ubuntu_ver \
                -f deploy/docker/Dockerfile.cpu \
                -t resilient-rap:cpu-ubuntu${ubuntu_ver} \
                . || echo "⚠ Failed: cpu-ubuntu${ubuntu_ver}"
        done
        
        echo ""
        echo "✓ All variants built"
        ;;
    
    *)
        echo "Usage: $0 {cuda|rocm|cpu|all} [CUDA_VERSION] [ROCM_VERSION] [UBUNTU_VERSION] [PYTORCH_VERSION]"
        echo ""
        echo "Examples:"
        echo "  $0 cuda 12.3.0"
        echo "  $0 cuda 12.4.0 6.0 24.04"
        echo "  $0 rocm 6.1"
        echo "  $0 cpu"
        echo "  $0 all"
        exit 1
        ;;
esac

echo ""
echo "=== Build Complete ==="
echo "List images: docker images | grep resilient-rap"
