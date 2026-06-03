#!/bin/bash

R2_BUCKET="https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models"
MODEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p $MODEL_DIR

echo "Downloading models from Cloudflare R2..."

echo "Downloading Gemma4 E4B..."
curl -L -o $MODEL_DIR/gemma4-e4b-it.gguf "$R2_BUCKET/gemma4-e4b-it.gguf"

echo "Downloading Gemma4 31B..."
curl -L -o $MODEL_DIR/gemma4-31b-gguf.gguf "$R2_BUCKET/gemma4-31b-gguf.gguf"

echo "Downloading BERT (all-MiniLM-L6-v2)..."
mkdir -p $MODEL_DIR/all-MiniLM-L6-v2
curl -L -o $MODEL_DIR/all-MiniLM-L6-v2/config.json "$R2_BUCKET/all-MiniLM-L6-v2/config.json"
curl -L -o $MODEL_DIR/all-MiniLM-L6-v2/model.safetensors "$R2_BUCKET/all-MiniLM-L6-v2/model.safetensors"
curl -L -o $MODEL_DIR/all-MiniLM-L6-v2/tokenizer.json "$R2_BUCKET/all-MiniLM-L6-v2/tokenizer.json"
curl -L -o $MODEL_DIR/all-MiniLM-L6-v2/tokenizer_config.json "$R2_BUCKET/all-MiniLM-L6-v2/tokenizer_config.json"
curl -L -o $MODEL_DIR/all-MiniLM-L6-v2/vocab.txt "$R2_BUCKET/all-MiniLM-L6-v2/vocab.txt"
curl -L -o $MODEL_DIR/all-MiniLM-L6-v2/special_tokens_map.json "$R2_BUCKET/all-MiniLM-L6-v2/special_tokens_map.json"
curl -L -o $MODEL_DIR/all-MiniLM-L6-v2/modules.json "$R2_BUCKET/all-MiniLM-L6-v2/modules.json"
curl -L -o $MODEL_DIR/all-MiniLM-L6-v2/sentence_bert_config.json "$R2_BUCKET/all-MiniLM-L6-v2/sentence_bert_config.json"

echo "All models downloaded to $MODEL_DIR"
