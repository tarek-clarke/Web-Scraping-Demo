#!/bin/bash
# LUMI HPC Setup Script for Resilient RAP Framework
# Usage: source setup-lumi.sh

set -e  # Exit on error

echo "=== LUMI HPC Setup for Resilient RAP Framework ==="

# Check if we're on LUMI
if [ ! -d "/appl" ]; then
    echo "ERROR: This script should only be run on LUMI HPC"
    exit 1
fi

# Load required modules
echo "Loading modules..."
module load LUMI/23.09
module load partition/G
module load lumi-multitorch/2.1.0-rocm5.6.1-python3.11.7

echo "✓ Modules loaded"
echo "  Python: $(python3 --version)"
echo "  PyTorch: $(python3 -c 'import torch; print(torch.__version__)')"
echo "  ROCm: $(python3 -c 'import torch; print(torch.version.hip if hasattr(torch.version, \"hip\") else \"N/A\")')"

# Create virtual environment (recommended)
VENV_DIR=".venv-lumi"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv $VENV_DIR
    echo "✓ Virtual environment created at $VENV_DIR"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source $VENV_DIR/bin/activate
echo "✓ Virtual environment activated"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing requirements..."
pip install -r requirements-lumi.txt

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Environment variables for LUMI:"
echo "  export IS_LUMI=1"
echo "  export HF_MODEL_ID=google/gemma-4-E4B-it"
echo "  export HF_TOKEN=<your_token>"
echo "  export CHAOS_MODEL_ID=Qwen/Qwen2.5-7B-Instruct"
echo "  export USE_LLM_CHAOS=true"
echo ""
echo "To run the framework:"
echo "  python3 run_matrix.py --max-packets-per-api 500 --chaos-rate 0.05 --repetitions 1"
echo ""
echo "To activate this environment later:"
echo "  source $VENV_DIR/bin/activate"
