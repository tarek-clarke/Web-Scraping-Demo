# Docker Version Compatibility Guide

## Supported Version Matrix

### CUDA Builds

| CUDA Version | Ubuntu | PyTorch Index | Tested GPUs |
|--------------|--------|---------------|-------------|
| 12.4.0 | 24.04, 26.04 | cu124 | RTX 5090, B300 |
| 12.8.0 | 24.04, 26.04 | cu128 | RTX 5090, B300 (latest stable) |
| 13.3.0 | 26.04 | default | RTX 5090, B300 (cutting-edge) |

### ROCm Builds

| ROCm Version | Ubuntu | Python | PyTorch | Tested GPUs |
|--------------|--------|--------|---------|-------------|
| 7.2.2 | 24.04 | 3.12 | 2.10.0 | MI300X, MI250X |
| 7.2.3 | 24.04 | 3.12 | 2.10.0 | MI300X, MI250X |
| 7.2.4 | 24.04 | 3.12 | 2.10.0 | MI300X, MI250X (latest) |

### CPU Builds

| Ubuntu | PyTorch Index | Use Case |
|--------|---------------|----------|
| 24.04 | cpu | Intel 12600K, fallback |
| 26.04 | cpu | Latest Ubuntu systems |

## Build Commands

### Single Build

```bash
# CUDA 13.3 + Ubuntu 26.04 (default)
./deploy/build-docker-matrix.sh cuda

# CUDA 12.8 + Ubuntu 26.04
./deploy/build-docker-matrix.sh cuda 12.8.0

# ROCm 7.2.4 + Ubuntu 24.04
./deploy/build-docker-matrix.sh rocm 13.3.0 7.2.4

# CPU + Ubuntu 26.04
./deploy/build-docker-matrix.sh cpu 13.3.0 7.2.4 26.04
```

### Build All Variants

```bash
./deploy/build-docker-matrix.sh all
```

This builds:
- 6 CUDA variants (3 CUDA versions × 2 Ubuntu versions)
- 3 ROCm variants (3 ROCm versions × 1 Ubuntu version)
- 2 CPU variants (2 Ubuntu versions)

## Hardware-Specific Recommendations

### NVIDIA GPUs

| GPU | Recommended CUDA | Ubuntu | Command |
|-----|------------------|--------|---------|
| RTX 5090 | 12.8.0 or 13.3.0 | 26.04 | `./build-docker-matrix.sh cuda 13.3.0` |
| A100 | 12.4.0 or 12.8.0 | 24.04 | `./build-docker-matrix.sh cuda 12.8.0` |
| H100 | 12.8.0 or 13.3.0 | 26.04 | `./build-docker-matrix.sh cuda 13.3.0` |
| GH200 | 12.8.0 | 26.04 | `./build-docker-matrix.sh cuda 12.8.0` |
| B300 | 13.3.0 | 26.04 | `./build-docker-matrix.sh cuda 13.3.0` |

### AMD GPUs

| GPU | Recommended ROCm | Ubuntu | Command |
|-----|------------------|--------|---------|
| 7900XT | 7.2.4 | 24.04 | `./build-docker-matrix.sh rocm 13.3.0 7.2.4` |
| MI250X | 7.2.4 | 24.04 | `./build-docker-matrix.sh rocm 13.3.0 7.2.4` |
| MI300X | 7.2.4 | 24.04 | `./build-docker-matrix.sh rocm 13.3.0 7.2.4` |

### CPU

| CPU | Ubuntu | Command |
|-----|--------|---------|
| Intel 12600K | 24.04 or 26.04 | `./build-docker-matrix.sh cpu 13.3.0 7.2.4 26.04` |
| Apple M4 | N/A (use native) | See `deploy/macos/setup_m4.sh` |

## Version Compatibility Notes

### CUDA Version Selection

- **CUDA 12.4**: Stable, widely supported (driver 550.54+)
- **CUDA 12.8**: Latest stable, RTX 5090/B300 (driver 560.35+)
- **CUDA 13.3**: Cutting-edge, newest GPUs (driver 570.86+)

### ROCm Version Selection

- **ROCm 7.2.2**: Stable, MI300X/MI250X
- **ROCm 7.2.3**: Improved performance
- **ROCm 7.2.4**: Latest, MI300X optimizations

### Ubuntu Version Selection

- **Ubuntu 24.04 LTS**: Widely supported, recommended for HPC
- **Ubuntu 26.04 LTS**: Latest, newest kernel and driver support

## Troubleshooting

### CUDA Version Mismatch

**Error**: `CUDA driver version is insufficient for CUDA runtime version`

**Solution**: Use older CUDA version matching your driver:
```bash
nvidia-smi  # Check driver version
./build-docker-matrix.sh cuda 12.4.0  # Use older CUDA
```

### ROCm PyTorch Not Found

**Error**: `No matching distribution found for torch`

**Solution**: ROCm 7.2.4 base image includes PyTorch 2.10.0 pre-installed:
```bash
docker run --rm resilient-rap:rocm-7.2.4-ubuntu24.04 python3 -c "import torch; print(torch.version.hip)"
```

### Ubuntu 26.04 Package Issues

**Error**: `Package python3.11 is not available`

**Solution**: Ubuntu 26.04 ships Python 3.12 by default. The Dockerfile uses Python 3.12:
```bash
./build-docker-matrix.sh cuda 13.3.0 7.2.4 26.04
```

## Testing Builds

```bash
# Test CUDA build
docker run --rm --gpus all resilient-rap:cuda-13.3.0-ubuntu26.04 \
    python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.version.cuda)"

# Test ROCm build
docker run --rm --device=/dev/kfd --device=/dev/dri resilient-rap:rocm-7.2.4-ubuntu24.04 \
    python3 -c "import torch; print('ROCm:', torch.cuda.is_available(), torch.version.hip)"

# Test CPU build
docker run --rm resilient-rap:cpu-ubuntu26.04 \
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
