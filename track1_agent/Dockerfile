FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app \
    LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    openai>=1.0.0 \
    huggingface-hub>=0.20.0 \
    numpy>=1.22.0

COPY track1_agent/agent.py /app/agent.py

CMD ["python3", "agent.py"]
