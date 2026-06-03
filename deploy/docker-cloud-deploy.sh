#!/bin/bash

set -e

echo "=== Resilient RAP Framework - Docker Cloud Deployment ==="

COMPOSE_FILE=${1:-docker-compose.cloud.yml}
HARDWARE_TYPE=${2:-cuda}
CUDA_VERSION=${3:-12.3.0}
ROCM_VERSION=${4:-6.0}
UBUNTU_VERSION=${5:-22.04}
PYTORCH_VERSION=${6:-2.1.1}

echo "Using compose file: $COMPOSE_FILE"
echo "Hardware type: $HARDWARE_TYPE"
echo "CUDA Version: $CUDA_VERSION"
echo "ROCm Version: $ROCM_VERSION"
echo "Ubuntu Version: $UBUNTU_VERSION"
echo "PyTorch Version: $PYTORCH_VERSION"
echo ""

export CUDA_VERSION
export ROCM_VERSION
export UBUNTU_VERSION
export PYTORCH_VERSION

echo "Building Docker image..."
docker-compose -f $COMPOSE_FILE build rap-$HARDWARE_TYPE

echo ""
echo "Downloading models from R2..."
docker-compose -f $COMPOSE_FILE run --rm rap-$HARDWARE_TYPE bash -c "
    mkdir -p /app/models &&
    cd /app/models &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/gemma4-e4b-it.gguf &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/gemma4-31b-gguf.gguf &&
    mkdir -p all-MiniLM-L6-v2 &&
    cd all-MiniLM-L6-v2 &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/all-MiniLM-L6-v2/config.json &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/all-MiniLM-L6-v2/model.safetensors &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/all-MiniLM-L6-v2/tokenizer.json &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/all-MiniLM-L6-v2/tokenizer_config.json &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/all-MiniLM-L6-v2/vocab.txt &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/all-MiniLM-L6-v2/special_tokens_map.json &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/all-MiniLM-L6-v2/modules.json &&
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/all-MiniLM-L6-v2/sentence_bert_config.json
"

echo ""
echo "Running ingestion (100k packets)..."
docker-compose -f $COMPOSE_FILE run --rm rap-$HARDWARE_TYPE bash -c "
    cd /app/go/ingestion &&
    go run main.go
"

echo ""
echo "Running matrix (60 combinations)..."
docker-compose -f $COMPOSE_FILE up rap-$HARDWARE_TYPE

echo ""
echo "=== Execution Complete ==="
echo "Results saved to Docker volume: rap-data"
echo "To copy results locally:"
echo "  docker cp rap-${HARDWARE_TYPE}-cloud:/app/data/reports ./data/reports"
