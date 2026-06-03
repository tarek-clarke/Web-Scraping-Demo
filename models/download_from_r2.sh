#!/bin/bash

R2_BUCKET="https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models"
MODEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p $MODEL_DIR

echo "Downloading Gemma4 models from Cloudflare R2..."

curl -L -o $MODEL_DIR/gemma4-e4b-it.gguf "$R2_BUCKET/gemma4-e4b-it.gguf"
curl -L -o $MODEL_DIR/gemma4-31b-gguf.gguf "$R2_BUCKET/gemma4-31b-gguf.gguf"

echo "Models downloaded to $MODEL_DIR"
