# Lightweight container for Track 1: Hybrid Token-Efficient Routing Agent
# Gemma 3 GGUF local models (zero Fireworks tokens) + Fireworks for complex tasks
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies for llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
# - llama-cpp-python: Local Gemma GGUF inference (0 Fireworks tokens)
# - qiskit + qiskit-aer: VQC quantum router (CPU simulator)
# - openai: Fireworks AI API client
# - numpy: Feature vector operations
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    llama-cpp-python>=0.2.0 \
    qiskit>=1.0.0 \
    qiskit-aer>=0.14.0 \
    openai>=1.0.0 \
    numpy>=1.22.0

# Copy Track 1 agent files
COPY track1_agent/agent.py /app/agent.py
COPY track1_agent/query_feature_extractor.py /app/query_feature_extractor.py

# Copy Gemma GGUF models (baked into image, 0 tokens at runtime)
COPY track1_agent/gemma_cache/ /app/gemma_cache/

# Run the agent pipeline
CMD ["python3", "agent.py"]
