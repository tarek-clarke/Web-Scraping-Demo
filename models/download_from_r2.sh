#!/bin/bash

R2_BUCKET="your-bucket-url"
MODEL_DIR="../../models"

mkdir -p $MODEL_DIR

echo "Downloading Gemma4 models from Cloudflare R2..."

curl -o $MODEL_DIR/gemma4-e4b-it.gguf "$R2_BUCKET/gemma4-e4b-it.gguf"
curl -o $MODEL_DIR/gemma4-31b-gguf.gguf "$R2_BUCKET/gemma4-31b-gguf.gguf"

echo "Models downloaded to $MODEL_DIR"
