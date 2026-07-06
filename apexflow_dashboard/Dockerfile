# Use official AMD ROCm PyTorch base image for native GPU acceleration
FROM rocm/pytorch:rocm-6.1-py3.10

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/hf_cache

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python packages
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

# Copy application files
COPY . /app

# Expose port
EXPOSE 5000

# Run Flask application
CMD ["python3", "app.py"]
