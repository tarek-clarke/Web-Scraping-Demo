# Heterogeneous Multi-Supercomputer Dockerfile for Resilient RAP Framework
# Optimized to bootstrap and run on:
# 1. LUMI (AMD Instinct MI250X - ROCm/HIP)
# 2. Jupiter (NVIDIA GH200 - CUDA)
# 3. Marenostrum (Heterogeneous CUDA/ROCm/CPU partitions)
# 4. IBM Quantum (Qiskit hardware runtime integration)

# Standardize on high-compatibility PyTorch base image
FROM pytorch/pytorch:2.4.1-cuda12.4-cudnn9-devel

USER root
ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies, compilers, and hardware diagnostic tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    ca-certificates \
    pciutils \
    kmod \
    lm-sensors \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements including Qiskit and CodeCarbon
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    numpy \
    pandas \
    scipy \
    scikit-learn \
    transformers \
    codecarbon \
    pynvml \
    qiskit \
    qiskit-aer \
    qiskit-ibm-runtime \
    Levenshtein \
    requests \
    httpx

# Configure dynamic hardware environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace
ENV HF_HOME=/workspace/hf_cache

# Create mountable workspace directories
WORKDIR /workspace
RUN mkdir -p /workspace/data /workspace/metrics /workspace/configs

# Setup bootstrap script to detect hardware capabilities and configure run backends
RUN echo '#!/bin/bash\n\
echo "=== Resilient RAP Multi-Supercomputer Bootstrapping ==="\n\
\n\
# 1. Detect Accelerator\n\
if command -v nvidia-smi &> /dev/null; then\n\
    echo "Detected NVIDIA GPU Architecture (CUDA)." \n\
    export ACCELERATOR_TYPE="CUDA"\n\
elif command -v rocm-smi &> /dev/null || [ -d /opt/rocm ]; then\n\
    echo "Detected AMD GPU Architecture (ROCm)." \n\
    export ACCELERATOR_TYPE="ROCm"\n\
    # Fix for unprivileged sysfs access on LUMI-G\n\
    export HSA_ENABLE_SDMA=0\n\
else\n\
    echo "No accelerator found. Falling back to CPU Mode." \n\
    export ACCELERATOR_TYPE="CPU"\n\
fi\n\
\n\
# 2. IBM Quantum API Key injection\n\
if [ -n "$IBM_QUANTUM_API_TOKEN" ]; then\n\
    echo "IBM Quantum API token detected. Initializing IBM Runtime integration..."\n\
    python3 -c "from qiskit_ibm_runtime import QiskitRuntimeService; QiskitRuntimeService.save_account(channel=\"ibm_quantum\", token=\"$IBM_QUANTUM_API_TOKEN\", overwrite=True)"\n\
else\n\
    echo "No IBM Quantum API Token provided. Simulator fallback active."\n\
fi\n\
\n\
# Execute user command\n\
exec "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "run_matrix.py"]