#!/bin/bash
set -e
MODEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Downloading models from HuggingFace..."

echo "BERT (all-MiniLM-L6-v2)..."
mkdir -p "$MODEL_DIR/bert-minilm-v2"
python3 -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
m.save('$MODEL_DIR/bert-minilm-v2')
"

echo "Gemma 4 E4B (4-bit, auto-downloads on first use)..."
echo "  Configured for HF transformers with 4-bit quantization."
echo "  Set HF_TOKEN for faster downloads."

echo "All models ready."
