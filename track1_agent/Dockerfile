FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir llama-cpp-python>=0.2.0

COPY track1_agent/agent.py /app/agent.py
COPY track1_agent/gemma_cache/google_gemma-3-4b-it-Q4_K_M.gguf /models/gemma-3-4b.q4.gguf

CMD ["python3", "agent.py"]
