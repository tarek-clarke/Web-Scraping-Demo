FROM rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_release_2.3.0

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    openai>=1.0.0 \
    transformers>=4.40.0 \
    accelerate>=0.25.0 \
    huggingface-hub>=0.20.0

COPY track1_agent/agent.py /app/agent.py

CMD ["python3", "agent.py"]
