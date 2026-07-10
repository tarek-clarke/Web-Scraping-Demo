FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    llama-cpp-python>=0.2.0 \
    openai>=1.0.0 \
    numpy>=1.22.0 \
    huggingface-hub>=0.20.0

COPY track1_agent/agent.py /app/agent.py

CMD ["python3", "agent.py"]
