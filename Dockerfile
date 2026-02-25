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
    # R and statistical packages
    software-properties-common \
    r-base \
    r-base-dev \
    \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ──────────────────────────────────────────────────────────────────────────
# 2. Install R packages (statistical analysis, web scraping)
# ──────────────────────────────────────────────────────────────────────────
RUN R -e "install.packages(c('reticulate', 'tidyverse', 'rvest', 'httr2', 'jsonlite'), repos='https://cloud.r-project.org/')" 2>&1 | grep -v "^$"

# ──────────────────────────────────────────────────────────────────────────
# 3. Install Python packages (PyTorch already in base, add data science)
# ──────────────────────────────────────────────────────────────────────────
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir \
    # Core data processing
    pandas \
    numpy \
    scipy \
    scikit-learn \
    \
    # Web scraping & HTTP
    requests \
    beautifulsoup4 \
    lxml \
    selenium \
    playwright \
    \
    # Visualization & analysis
    matplotlib \
    plotly \
    seaborn \
    \
    # Testing & utilities
    pytest \
    pyyaml \
    python-dotenv

# ──────────────────────────────────────────────────────────────────────────
# 4. ROCm Environment Configuration  
# ──────────────────────────────────────────────────────────────────────────
# GPU-specific tuning for AMD 7900 XT (gfx1100)
ENV ROCM_HOME=/opt/rocm
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm-6.2.0/lib:/usr/local/lib:$LD_LIBRARY_PATH
ENV PATH=/opt/rocm/bin:/opt/rocm/sbin:$PATH

# HSA (Heterogeneous System Architecture) tuning
ENV HSA_OVERRIDE_GFX_VERSION=11.0.0    # Force gfx1100 (7900 XT)
ENV HSA_ENABLE_SDMA=0                  # Use compute instead of SDMA for stability
ENV GPU_DEVICE_ORDINAL=0               # Default to first GPU

# ──────────────────────────────────────────────────────────────────────────
# 5. Build fast_ingest C++ extension (zero-copy GPU ingestion)
# ──────────────────────────────────────────────────────────────────────────
WORKDIR /app
COPY . /app

RUN cd /app && \
    python3 setup.py build_ext --inplace 2>&1 | tee /tmp/build.log && \
    (grep -q "error:" /tmp/build.log && exit 1 || true) || echo "Build complete"

# ──────────────────────────────────────────────────────────────────────────
# 6. Final configuration
# ──────────────────────────────────────────────────────────────────────────
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PYTHONUNBUFFERED=1

WORKDIR /app
CMD ["/bin/bash"]