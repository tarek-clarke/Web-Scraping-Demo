# Lightweight container for Track 1: Hybrid Token-Efficient Routing Agent
# Uses python:3.10-slim (NOT the heavy ROCm image) since Track 1 runs
# on the standardized scoring environment, not custom GPU hardware.
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/hf_cache

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
# - qiskit + qiskit-aer: VQC quantum router (runs on CPU simulator)
# - openai: Fireworks AI API client
# - numpy: Feature vector operations
# - transformers + torch: Local model inference (optional, for GPU nodes)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    qiskit>=1.0.0 \
    qiskit-aer>=0.14.0 \
    openai>=1.0.0 \
    numpy>=1.22.0 \
    transformers>=4.40.0 \
    torch>=2.0.0 \
    accelerate>=0.25.0

# Copy Track 1 agent files
COPY track1_agent/ /app/

# Expose API port
EXPOSE 8080

# Run the agent pipeline
CMD ["python3", "agent.py"]
