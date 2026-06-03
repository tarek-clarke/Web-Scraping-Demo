#!/bin/bash

R2_BUCKET="https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models"
MODEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p $MODEL_DIR

echo "Downloading models from Cloudflare R2..."

echo "Downloading Qwen2.5-7B (chaos generator)..."
curl -L -o $MODEL_DIR/Qwen2.5-7B-Instruct-Q4_K_M.gguf "$R2_BUCKET/Qwen2.5-7B-Instruct-Q4_K_M.gguf"

echo "Downloading Gemma4 E4B (reconciler)..."
mkdir -p $MODEL_DIR/gemma-4-e4b-it
curl -L -o $MODEL_DIR/gemma-4-e4b-it/Q4_K_M.gguf "$R2_BUCKET/gemma-4-e4b-it/Q4_K_M.gguf"

echo "Downloading Gemma4 31B (reconciler)..."
curl -L -o $MODEL_DIR/gemma-4-31B-it-Q4_K_M.gguf "$R2_BUCKET/gemma-4-31B-it-Q4_K_M.gguf"

echo "Downloading BERT (all-MiniLM-L6-v2)..."
mkdir -p $MODEL_DIR/bert-minilm-v2
curl -L -o $MODEL_DIR/bert-minilm-v2/config.json "$R2_BUCKET/bert-minilm-v2/config.json"
curl -L -o $MODEL_DIR/bert-minilm-v2/config_sentence_transformers.json "$R2_BUCKET/bert-minilm-v2/config_sentence_transformers.json"
curl -L -o $MODEL_DIR/bert-minilm-v2/model.safetensors "$R2_BUCKET/bert-minilm-v2/model.safetensors"
curl -L -o $MODEL_DIR/bert-minilm-v2/modules.json "$R2_BUCKET/bert-minilm-v2/modules.json"
curl -L -o $MODEL_DIR/bert-minilm-v2/sentence_bert_config.json "$R2_BUCKET/bert-minilm-v2/sentence_bert_config.json"
curl -L -o $MODEL_DIR/bert-minilm-v2/special_tokens_map.json "$R2_BUCKET/bert-minilm-v2/special_tokens_map.json"
curl -L -o $MODEL_DIR/bert-minilm-v2/tokenizer.json "$R2_BUCKET/bert-minilm-v2/tokenizer.json"
curl -L -o $MODEL_DIR/bert-minilm-v2/tokenizer_config.json "$R2_BUCKET/bert-minilm-v2/tokenizer_config.json"
curl -L -o $MODEL_DIR/bert-minilm-v2/vocab.txt "$R2_BUCKET/bert-minilm-v2/vocab.txt"

echo "All models downloaded to $MODEL_DIR"
