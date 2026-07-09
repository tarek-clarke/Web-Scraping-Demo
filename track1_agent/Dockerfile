# Stage 1: Build llama-cpp-python wheel with HIPBLAS in ROCm image
FROM rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_release_2.3.0 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

ENV CMAKE_ARGS="-DGGML_HIPBLAS=on"
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip wheel --no-cache-dir --no-deps --wheel-dir=/wheels llama-cpp-python>=0.2.0

# Stage 2: Slim runtime — assumes /opt/rocm exists on scoring env
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    openai>=1.0.0 \
    numpy>=1.22.0 \
    huggingface-hub>=0.20.0 \
    qiskit>=1.0.0 \
    qiskit-aer>=0.14.0

# Copy and install the HIPBLAS-compiled wheel from builder
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

COPY track1_agent/agent.py /app/agent.py
COPY track1_agent/query_feature_extractor.py /app/query_feature_extractor.py
COPY track1_agent/vqc_parameters.json /app/vqc_parameters.json

CMD ["python3", "agent.py"]
