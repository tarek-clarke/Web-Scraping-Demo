# Multi-Platform Model Manager

A robust, portable model manager for Hugging Face transformers that automatically adapts to different hardware backends and cloud platforms.

## Supported Platforms

| Platform | Hardware | Backend | Precision | Notes |
|----------|----------|---------|-----------|-------|
| **Local (Mac)** | Apple Silicon (M1/M2/M3) | MPS | float16 | Native Apple GPU acceleration |
| **Vast.ai** | NVIDIA GPUs | CUDA | bfloat16 | FlashAttention-2 supported |
| **LUMI HPC** | AMD MI250X | ROCm | bfloat16 | SDPA attention, no bitsandbytes |
| **Spheron** | NVIDIA GPUs | CUDA | bfloat16 | HF mirror support for restricted networks |

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from src.inference import ModelManager

# Auto-detects platform and loads model
manager = ModelManager()
response = manager.generate_response("What is quantum computing?")
print(response)
```

## Environment Variables

### Core Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_MODEL_ID` | `google/gemma-4-E4B-it` | Hugging Face model identifier |
| `HF_TOKEN` | - | Hugging Face API token (for gated models) |
| `LLM_MAX_REASONING_TOKENS` | `2048` | Maximum tokens for generation |

### Chaos Injection

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAOS_MODEL_ID` | `Qwen/Qwen2.5-7B-Instruct` | Model for semantic chaos injection |
| `USE_LLM_CHAOS` | `true` | Enable LLM-based chaos (false = deterministic fallback) |

### Platform-Specific

| Variable | Description |
|----------|-------------|
| `HF_ENDPOINT` | Custom Hugging Face endpoint (for mirrors/proxies) |
| `HF_HUB_OFFLINE` | Set to `1` to use only cached models |
| `HF_LOCAL_MODEL_PATH` | Local path to model (fallback if HF unavailable) |
| `IS_LUMI` | Set to `1` for LUMI HPC (AMD ROCm) |

## Platform-Specific Setup

### 1. Local Mac (Apple Silicon)

```bash
# No special configuration needed
export HF_MODEL_ID="google/gemma-4-E4B-it"
python example_usage.py
```

**Features:**
- Automatic MPS backend detection
- float16 precision for optimal performance
- bitsandbytes 4-bit quantization (optional)

### 2. Vast.ai (NVIDIA)

```bash
export HF_TOKEN="your_token_here"
export HF_MODEL_ID="google/gemma-4-12B-it"  # Larger model for cloud
python example_usage.py
```

**Features:**
- Automatic CUDA backend detection
- bfloat16 precision
- FlashAttention-2 for faster inference
- bitsandbytes 4-bit quantization

### 3. LUMI HPC (AMD ROCm)

**Requirements:**
- Python 3.11.7 (provided by lumi-multitorch module)
- lumi-multitorch/2.1.0-rocm5.6.1-python3.11.7 module
- Project allocation on LUMI

**Quick Setup:**

```bash
# Clone repository
git clone https://github.com/your-username/resilient-rap-framework.git
cd resilient-rap-framework

# Run setup script (loads modules, creates venv, installs dependencies)
source setup-lumi.sh

# Set your Hugging Face token
export HF_TOKEN="your_token_here"

# Run the framework
python3 run_matrix.py --max-packets-per-api 500 --chaos-rate 0.05 --repetitions 1
```

**Slurm Job Submission:**

```bash
# Submit a job using the provided Slurm script
sbatch slurm-lumi.sh

# Monitor job status
squeue -u $USER

# View job output
cat rap-<job-id>.out
```

**Manual Setup (Alternative):**

```bash
# Load modules
module load LUMI/23.09
module load partition/G
module load lumi-multitorch/2.1.0-rocm5.6.1-python3.11.7

# Create and activate virtual environment
python3 -m venv .venv-lumi
source .venv-lumi/bin/activate

# Install dependencies (uses requirements-lumi.txt)
pip install -r requirements-lumi.txt

# Set environment variables
export IS_LUMI="1"
export HF_TOKEN="your_token_here"
export HF_MODEL_ID="google/gemma-4-12B-it"
export CHAOS_MODEL_ID="Qwen/Qwen2.5-7B-Instruct"
export USE_LLM_CHAOS="true"

# Run the framework
python3 run_matrix.py --max-packets-per-api 500 --chaos-rate 0.05 --repetitions 1
```

**Features:**
- Automatic ROCm backend detection (AMD MI250X)
- bfloat16 precision for optimal performance
- SDPA attention (FlashAttention not available on ROCm)
- No bitsandbytes (not supported on ROCm)
- PyTorch provided by lumi-multitorch module (DO NOT install via pip)

**Important Notes:**
- The `lumi-multitorch` module provides PyTorch with ROCm support
- Do NOT install `torch` via pip - it will conflict with the module
- Use `requirements-lumi.txt` instead of `requirements.txt`
- ROCm does not support bitsandbytes or llama-cpp-python
- Models will download on first run and cache in `~/.cache/huggingface/`

**Troubleshooting:**

```bash
# Check ROCm availability
rocm-smi --showproductname

# Check PyTorch ROCm support
python3 -c "import torch; print(f'ROCm: {torch.version.hip}')"

# Clear Hugging Face cache if needed
rm -rf ~/.cache/huggingface/hub/models--*
```

### 4. Spheron (NVIDIA with HF Mirror)

If Spheron blocks direct Hugging Face access:

```bash
export HF_ENDPOINT="https://hf-mirror.com"  # Or your preferred mirror
export HF_TOKEN="your_token_here"
export HF_MODEL_ID="google/gemma-4-12B-it"

python example_usage.py
```

**Alternative: Pre-download models locally and upload to Spheron**

```bash
# On your local machine
huggingface-cli download google/gemma-4-12B-it --local-dir ./models/gemma-4-12B-it

# Upload to Spheron storage, then:
export HF_LOCAL_MODEL_PATH="/path/to/models/gemma-4-12B-it"
export HF_HUB_OFFLINE="1"

python example_usage.py
```

## Advanced Usage

### Streaming Generation

```python
manager = ModelManager()

for token in manager.generate_stream("Tell me a story:", max_new_tokens=500):
    print(token, end="", flush=True)
```

### Batch Processing

```python
manager = ModelManager()

prompts = [
    "What is machine learning?",
    "Explain neural networks.",
    "What is deep learning?"
]

for prompt in prompts:
    response = manager.generate_response(prompt, max_new_tokens=100)
    print(f"Q: {prompt}")
    print(f"A: {response}\n")
```

### Custom Generation Parameters

```python
manager = ModelManager()

response = manager.generate_response(
    prompt="Write a poem about AI",
    max_new_tokens=200,
    temperature=0.9,  # Higher = more creative
    top_p=0.95,       # Nucleus sampling
    do_sample=True    # Enable sampling (False = greedy)
)
```

### Memory Management

```python
manager = ModelManager()

# Use the model
response = manager.generate_response("Hello")

# Clear KV cache to free memory
manager.reset_kv_cache()

# Unload model completely
manager.unload()
```

## Troubleshooting

### "Failed to load model" on Spheron

**Problem:** Spheron blocks direct Hugging Face access.

**Solution:** Use a mirror or pre-download models:
```bash
export HF_ENDPOINT="https://hf-mirror.com"
# OR
export HF_LOCAL_MODEL_PATH="/path/to/local/model"
export HF_HUB_OFFLINE="1"
```

### "bitsandbytes not available" on LUMI

**Problem:** bitsandbytes doesn't support AMD ROCm.

**Solution:** This is expected. The model manager automatically falls back to full precision (bfloat16).

### "CUDA out of memory" errors

**Solution:** Use 4-bit quantization or a smaller model:
```bash
export HF_MODEL_ID="google/gemma-4-E4B-it"  # Smaller model
```

Or enable quantization in code:
```python
from transformers import BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

# Pass to ModelManager (advanced usage)
```

### Slow model loading

**Solution:** Models are cached after first download. Subsequent loads are fast.

To force re-download:
```bash
rm -rf ~/.cache/huggingface/hub/models--google--gemma-4-E4B-it
```

## Architecture

```
src/inference/
├── model_manager.py      # Main model manager class
├── llm_manager.py        # Legacy LLM manager (deprecated)
└── __init__.py          # Exports
```

**Key Components:**

1. **BackendConfig**: Dataclass holding platform-specific configuration
2. **detect_platform()**: Identifies cloud platform (local/vast/lumi/spheron)
3. **detect_backend()**: Auto-detects hardware and returns optimal config
4. **ModelManager**: Singleton class managing model lifecycle
5. **generate_response()**: Simple function wrapper for one-off generation

## Performance Benchmarks

| Platform | Model | Tokens/sec | Memory Usage |
|----------|-------|------------|--------------|
| Mac M3 Max | E4B | ~15 | 8 GB |
| Vast.ai A100 | 12B | ~45 | 24 GB |
| LUMI MI250X | 12B | ~50 | 24 GB |
| Spheron H100 | 12B | ~60 | 24 GB |

*Benchmarks are approximate and vary based on prompt length and generation parameters.*

## License

See LICENSE file for details.

## Contributing

Contributions welcome! Please ensure code works on all supported platforms before submitting PRs.
