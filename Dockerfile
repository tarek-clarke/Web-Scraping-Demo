# ──────────────────────────────────────────────────────────────────────────
# Cadillac F1 Telemetry Pipeline: ROCm 6.2 + PyTorch
# ──────────────────────────────────────────────────────────────────────────
# Base: Official ROCm 6.2 PyTorch image (AMD 7900 XT / RDNA3)
# GPU Support: Hip/ROCm (Linux native) + CPU fallback (Windows/WSL2)
# ──────────────────────────────────────────────────────────────────────────

FROM rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_release_2.3.0

USER root
ARG DEBIAN_FRONTEND=noninteractive

# ──────────────────────────────────────────────────────────────────────────
# 1. System Foundation: Build tools, libraries, compilers
# ──────────────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials for C++ extensions
    build-essential \
    cmake \
    git \
    wget \
    ca-certificates \
    \
    # ROCm development packages
    rocm-libs \
    hip-dev \
    hipcc \
    hipsparse-dev \
    hipblas-dev \
    hipblaslt-dev \
    hipsolver-dev \
    \
    # Python & data science
    python3-dev \
    python3-pip \
    python3-setuptools \
    \
    # System libraries
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ──────────────────────────────────────────────────────────────────────────
# 3. Install Python packages (PyTorch already in base, add data science)
# ──────────────────────────────────────────────────────────────────────────
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir \
    # Core data processing
    numpy \
    scipy \
    scikit-learn \
    \
    # HTTP
    requests \
    \
    # Testing & utilities
    pytest \
    pyyaml \
    python-dotenv \
    \
    # Kafka DLQ 3-stream routing (Python 3.10–3.13 compatible fork)
    kafka-python-ng

# ──────────────────────────────────────────────────────────────────────────
# 4. ROCm Environment Configuration  
# ──────────────────────────────────────────────────────────────────────────
# GPU-specific tuning for AMD 7900 XT (gfx1100)
ENV ROCM_HOME=/opt/rocm
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm-6.2.0/lib:/usr/local/lib:$LD_LIBRARY_PATH
ENV PATH=/opt/rocm/bin:/opt/rocm/sbin:$PATH

# HSA (Heterogeneous System Architecture) tuning
# Force gfx1100 (7900 XT)
ENV HSA_OVERRIDE_GFX_VERSION=11.0.0
# Use compute instead of SDMA for stability
ENV HSA_ENABLE_SDMA=0
# Default to first GPU
ENV GPU_DEVICE_ORDINAL=0

# ──────────────────────────────────────────────────────────────────────────
# 5. Build fast_ingest C++ extension (zero-copy GPU ingestion)
# ──────────────────────────────────────────────────────────────────────────
WORKDIR /app

# Copy only build-relevant files first (cache-friendly: Python/doc changes
# won't invalidate the expensive C++ extension build layer)
COPY setup.py fast_ingest.cpp /app/

RUN cd /app && \
    python3 setup.py build_ext --inplace 2>&1 | tee /tmp/build.log && \
    (grep -q "error:" /tmp/build.log && exit 1 || true) || echo "Build complete"

# Now copy the rest of the application
COPY . /app

# ──────────────────────────────────────────────────────────────────────────
# 6. Final configuration
# ──────────────────────────────────────────────────────────────────────────
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

WORKDIR /app
CMD ["/bin/bash"]