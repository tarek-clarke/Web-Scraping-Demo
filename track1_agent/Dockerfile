FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:$LD_LIBRARY_PATH

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    openai>=1.0.0 \
    numpy>=1.22.0 \
    huggingface-hub>=0.20.0 \
    qiskit>=1.0.0 \
    qiskit-aer>=0.14.0

COPY track1_agent/agent.py /app/agent.py
COPY track1_agent/query_feature_extractor.py /app/query_feature_extractor.py
COPY track1_agent/vqc_parameters.json /app/vqc_parameters.json

CMD ["python3", "agent.py"]
