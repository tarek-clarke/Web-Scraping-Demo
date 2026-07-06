# ApexFlow AI — Track 3: Unicorn Track
# Full AMD ROCm PyTorch base for native GPU acceleration on Instinct MI300X
FROM rocm/pytorch:rocm-6.1-py3.10

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/hf_cache

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    Flask>=3.0.0 \
    openai>=1.0.0 \
    numpy>=1.22.0 \
    pandas>=2.0.0 \
    transformers>=4.40.0 \
    qiskit>=1.0.0 \
    qiskit-aer>=0.14.0 \
    Levenshtein>=0.20.0

# Copy the routing module from the repo root
COPY src/ /app/src/

# Copy dashboard application files
COPY apexflow_dashboard/app.py /app/app.py
COPY apexflow_dashboard/static/ /app/static/

# Expose port
EXPOSE 5000

# Run Flask application
CMD ["python3", "app.py"]
