# Docker Version Compatibility Guide

## Supported Version Matrix

### CUDA Builds

| CUDA Version | Ubuntu | PyTorch Index | Tested GPUs |
|--------------|--------|---------------|-------------|
| 11.8.0 | 22.04, 24.04 | cu118 | RTX 3090, A100 (older drivers) |
| 12.1.0 | 22.04, 24.04 | cu121 | RTX 4090, A100, H100 |
| 12.3.0 | 22.04, 24.04 | cu121 | RTX 5090, H100, GH200 |
| 12.4.0 | 22.04, 24.04 | cu124 | RTX 5090, B300 (latest) |

### ROCm Builds

| ROCm Version | Ubuntu | PyTorch Index | Tested GPUs |
|--------------|--------|---------------|-------------|
| 6.0 | 22.04 | rocm6.0 | MI250X, 7900XT |
| 6.1 | 22.04 | rocm6.1 | MI250X, MI300X |
| 6.2 | 22.04 | rocm6.1 | MI300X (latest) |

### CPU Builds

| Ubuntu | PyTorch Index | Use Case |
|--------|---------------|----------|
| 22.04 | cpu | Intel 12600K, fallback |
| 24.04 | cpu | Latest Ubuntu systems |

## Build Commands

### Single Build

```bash
# CUDA 12.3 + Ubuntu 22.04 (default)
./deploy/build-docker-matrix.sh cuda

# CUDA 12.4 + Ubuntu 24.04
./deploy/build-docker-matrix.sh cuda 12.4.0 6.0 24.04

# ROCm 6.1 + Ubuntu 22.04
./deploy/build-docker-matrix.sh rocm 12.3.0 6.1

# CPU + Ubuntu 24.04
./deploy/build-docker-matrix.sh cpu 12.3.0 6.0 24.04
```

### Build All Variants

```bash
./deploy/build-docker-matrix.sh all
```

This builds:
- 8 CUDA variants (4 CUDA versions × 2 Ubuntu versions)
- 3 ROCm variants (3 ROCm versions × 1 Ubuntu version)
- 2 CPU variants (2 Ubuntu versions)

## Hardware-Specific Recommendations

### NVIDIA GPUs

| GPU | Recommended CUDA | Ubuntu | Command |
|-----|------------------|--------|---------|
| RTX 5090 | 12.3.0 or 12.4.0 | 22.04 | `./build-docker-matrix.sh cuda 12.4.0` |
| A100 | 12.1.0 or 12.3.0 | 22.04 | `./build-docker-matrix.sh cuda 12.3.0` |
| H100 | 12.3.0 or 12.4.0 | 22.04 | `./build-docker-matrix.sh cuda 12.4.0` |
| GH200 | 12.3.0 | 22.04 | `./build-docker-matrix.sh cuda 12.3.0` |
| B300 | 12.4.0 | 24.04 | `./build-docker-matrix.sh cuda 12.4.0 6.0 24.04` |

### AMD GPUs

| GPU | Recommended ROCm | Ubuntu | Command |
|-----|------------------|--------|---------|
| 7900XT | 6.0 or 6.1 | 22.04 | `./build-docker-matrix.sh rocm 12.3.0 6.1` |
| MI250X | 6.0 | 22.04 | `./build-docker-matrix.sh rocm 12.3.0 6.0` |
| MI300X | 6.1 or 6.2 | 22.04 | `./build-docker-matrix.sh rocm 12.3.0 6.2` |

### CPU

| CPU | Ubuntu | Command |
|-----|--------|---------|
| Intel 12600K | 22.04 or 24.04 | `./build-docker-matrix.sh cpu 12.3.0 6.0 24.04` |
| Apple M4 | N/A (use native) | See `deploy/macos/setup_m4.sh` |

## Version Compatibility Notes

### CUDA Version Selection

- **CUDA 11.8**: Legacy support, older drivers (450.80+)
- **CUDA 12.1**: Stable, widely supported (driver 525.60+)
- **CUDA 12.3**: Latest stable (driver 535.86+)
- **CUDA 12.4**: Cutting-edge, RTX 5090/B300 (driver 550.54+)

### ROCm Version Selection

- **ROCm 6.0**: Stable, MI250X/7900XT
- **ROCm 6.1**: Improved MI300X support
- **ROCm 6.2**: Latest, MI300X optimizations

### Ubuntu Version Selection

- **Ubuntu 22.04 LTS**: Widely supported, recommended for HPC
- **Ubuntu 24.04 LTS**: Latest, may have newer driver support

## Troubleshooting

### CUDA Version Mismatch

**Error**: `CUDA driver version is insufficient for CUDA runtime version`

**Solution**: Use older CUDA version matching your driver:
```bash
nvidia-smi  # Check driver version
./build-docker-matrix.sh cuda 12.1.0  # Use older CUDA
```

### ROCm PyTorch Not Found

**Error**: `No matching distribution found for torch`

**Solution**: ROCm 6.2 uses ROCm 6.1 index:
```bash
# Already handled in Dockerfile, but verify:
docker run --rm resilient-rap:rocm-6.2-ubuntu22.04 python3 -c "import torch; print(torch.version.hip)"
```

### Ubuntu 24.04 Package Issues

**Error**: `Package python3.11 is not available`

**Solution**: Ubuntu 24.04 ships Python 3.12 by default. Update Dockerfile or use 22.04:
```bash
./build-docker-matrix.sh cuda 12.3.0 6.0 22.04
```

## Testing Builds

```bash
# Test CUDA build
docker run --rm --gpus all resilient-rap:cuda-12.3.0-ubuntu22.04 \
    python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.version.cuda)"

# Test ROCm build
docker run --rm --device=/dev/kfd --device=/dev/dri resilient-rap:rocm-6.0-ubuntu22.04 \
    python3 -c "import torch; print('ROCm:', torch.cuda.is_available(), torch.version.hip)"

# Test CPU build
docker run --rm resilient-rap:cpu-ubuntu22.04 \
    python3 -c "import torch; print('CPU:', not torch.cuda.is_available())"
```

## Image Tags

All images are tagged with version information:
- `resilient-rap:cuda-{CUDA_VERSION}-ubuntu{UBUNTU_VERSION}`
- `resilient-rap:rocm-{ROCM_VERSION}-ubuntu{UBUNTU_VERSION}`
- `resilient-rap:cpu-ubuntu{UBUNTU_VERSION}`

List all built images:
```bash
docker images | grep resilient-rap
```
