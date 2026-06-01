#!/bin/bash
# ==============================================================================
# VAST.AI RTX 5090 RAPID BENCHMARK SETUP SCRIPT (SECURE PROMPT)
# ==============================================================================
# Automatically prompts for your Hugging Face token at runtime, 
# installs dependency environments, downloads BERT, Gemma 4B, and the gated 
# Gemma 31B MoE model, and readies the instance for the 80-run sweep.
# ==============================================================================

set -e

echo "================================================================================"
echo "[*] SECURE HF AUTHENTICATION PROMPT"
echo "================================================================================"
# Securely prompt the user for their Hugging Face Access Token
read -sp "Enter your Hugging Face Access Token: " HF_TOKEN
echo ""

if [ -z "$HF_TOKEN" ]; then
    echo "[!] Error: No Hugging Face token entered. Aborting setup."
    exit 1
fi

echo "\n================================================================================"
echo "[*] Starting Vast.ai RTX 5090 Environment Initialization..."
echo "================================================================================"

# 1. Update package lists and install essential utilities
echo "\n[*] Installing system dependencies (git, build-essential)..."
apt-get update && apt-get install -y git build-essential curl python3-pip python3-venv

# 2. Upgrade pip and install core deep learning packages
echo "\n[*] Installing Python CUDA environment and Hugging Face SDK..."
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers huggingface_hub accelerate psutil sentence-transformers

# 3. Log in to Hugging Face using the provided Token (grants gated model access)
echo "\n[*] Authenticating with Hugging Face Hub..."
huggingface-cli login --token "$HF_TOKEN"

# 4. Pre-download models directly to the Vast.ai instance cache at high speeds
echo "\n[*] Downloading BERT Reconciler model (sentence-transformers/all-MiniLM-L6-v2)..."
python3 -c "
from sentence_transformers import SentenceTransformer
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print('[✓] BERT Downloaded!')
"

echo "\n[*] Downloading Gemma 4B E4B Instruct model (google/gemma-4-E4B-it)..."
python3 -c "
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
AutoTokenizer.from_pretrained('google/gemma-4-E4B-it')
AutoModelForCausalLM.from_pretrained('google/gemma-4-E4B-it', torch_dtype=torch.bfloat16)
print('[✓] Gemma 4B Downloaded!')
"

echo "\n[*] Downloading Gated Gemma 31B (AWQ 4-Bit) model (MaziyarPanahi/gemma-4-31b-it-AWQ)..."
python3 -c "
from transformers import AutoTokenizer, AutoModelForCausalLM
AutoTokenizer.from_pretrained('MaziyarPanahi/gemma-4-31b-it-AWQ')
AutoModelForCausalLM.from_pretrained('MaziyarPanahi/gemma-4-31b-it-AWQ')
print('[✓] Gemma 31B (AWQ) Downloaded!')
"

# 5. Optional: Install vLLM for high-speed continuous batching serving
echo "\n[*] Installing high-performance vLLM engine..."
pip install vllm || echo "[!] Warning: vLLM installation failed, running via PyTorch backend fallback."

echo "\n================================================================================"
echo "[✓] VAST.AI SETUP COMPLETED SUCCESSFULLY!"
echo "================================================================================"
echo "To launch the high-throughput vLLM server on your RTX 5090, run:"
echo "  python3 -m vllm.entrypoints.openai.api_server --model google/gemma-4-31B-it --quantization awq --port 8000"
echo ""
echo "To execute the sweep matrix with Gemma 31B enabled, run:"
echo "  export USE_GEMMA_30B=1"
echo "  python3 run_matrix_unified.py"
echo "================================================================================"
