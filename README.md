# Resilient RAP Framework

**Resilient API Adaptation Protocol** - End-to-end chaos engineering and reconciliation framework for telemetry data streams.

## Overview

Executes 60-combination matrix: **4 APIs × 3 Chaos Types × 5 Reconcilers** across heterogeneous hardware platforms.

### Components

- **Ingestion**: Go-based async streaming from 4 live APIs (OpenF1, Finnhub, SpaceX, OpenMeteo) at 100Hz
- **Chaos Engineering**: 5% injection rate via Gemma4-e4b-it, JSON manipulation, schema alteration
- **Reconciliation**: Levenshtein, Regex, BERT (MiniLM-v2), Gemma4-E4B-it, Gemma4-31b-gguf
- **Hardware Detection**: Auto-bootstrap for CUDA, ROCm, Apple Silicon, CPU with VRAM probing

### Target Volume

- **100,000 packets** total (25,000 per API source)
- **5,000 chaos injections** (5% of total)

## Hardware Matrix

| Platform | Type | VRAM | Concurrent Runs | Batch Size | Setup Method |
|----------|------|------|-----------------|------------|--------------|
| Intel 12600K | CPU | 0 GB | 4 | 4 | Docker CPU |
| AMD 7900XT | ROCm | 20 GB | 2 | 8 | Docker ROCm |
| Apple M4 | Silicon | 16 GB | 3 | 8 | Native Shell |
| NVIDIA H100 | CUDA | 80 GB | 8 | 32 | Docker CUDA |
| NVIDIA A100 | CUDA | 80 GB | 8 | 32 | Slurm (TalTech) |
| NVIDIA RTX 5090 | CUDA | 32 GB | 3 | 16 | Docker CUDA |
| NVIDIA RTX 6000 Blackwell WS | CUDA | 96 GB | 12 | 32 | Docker CUDA |
| NVIDIA GH200 | CUDA | 96 GB | 10 | 32 | Docker CUDA |
| NVIDIA B300 | CUDA | 288 GB | 20 | 64 | Docker CUDA |
| AMD MI250X | ROCm | 128 GB | 12 | 32 | Slurm (LUMI) |

## Quick Start

### 1. Clone and Setup

```bash
git clone <repo-url>
cd resilient-data
git checkout domain_testing
```

### 2. Detect Hardware

```bash
./deploy/detect_hardware.sh
```

This detects your GPU (NVIDIA/AMD/Apple Silicon) and recommends the correct CUDA/ROCm version and build command.

### 3. Download Models

Edit `models/download_from_r2.sh` with your Cloudflare R2 bucket URL:

```bash
chmod +x models/download_from_r2.sh
./models/download_from_r2.sh
```

### 4. Run Ingestion (Go)

```bash
cd go/ingestion
go mod download
go run main.go
cd ../..
```

This generates `data/ingested/telemetry_<timestamp>.json` with 100k packets.

### 5. Run Matrix (Python)

```bash
python3 run_matrix.py
```

Auto-detects hardware, probes VRAM, executes 60-combination matrix.

## Cloud GPU (Vast.ai / Spheron)

Single command for any NVIDIA GPU instance (RTX 5090, A100, H100, etc.):

```bash
git clone https://github.com/tarek-clarke/resilient-rap-framework.git && \
  cd resilient-rap-framework && git checkout domain_testing && cd deploy && \
  CUDA_VERSION=13.3.0 docker-compose -f docker-compose.cloud.yml build rap-cuda && \
  docker-compose -f docker-compose.cloud.yml run --rm rap-cuda bash -c "\
    cd /app/models && \
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/gemma4-e4b-it.gguf && \
    curl -L -O https://pub-66196916eecb44259146d96cf3604b80.r2.dev/models/gemma4-31b-gguf.gguf" && \
  docker-compose -f docker-compose.cloud.yml run --rm rap-cuda bash -c "cd /app/go/ingestion && go run main.go" && \
  docker-compose -f docker-compose.cloud.yml up rap-cuda
```

This builds the image, downloads models, ingests 100k packets, and runs the 60-combination matrix. Results saved to Docker volume. Copy locally with:

```bash
docker cp rap-cuda-cloud:/app/data/reports ./data/reports
```

**CUDA version tips**:
- RTX 5090 / B300 → `CUDA_VERSION=13.3.0`
- A100 / H100 / GH200 → `CUDA_VERSION=12.8.0`
- RTX 3090 / older drivers → `CUDA_VERSION=12.4.0`

## Platform-Specific Instructions

### NVIDIA CUDA (H100, A100, RTX 5090, RTX 6000, GH200, B300)

#### Docker

```bash
docker build -f deploy/docker/Dockerfile.cuda -t rap-cuda .
docker run --gpus all -v $(pwd)/data:/app/data rap-cuda
```

#### Slurm (TalTech A100)

```bash
sbatch deploy/slurm/taltech_a100.slurm
```

### AMD ROCm (7900XT, MI250X)

#### Docker

```bash
docker build -f deploy/docker/Dockerfile.rocm -t rap-rocm .
docker run --device=/dev/kfd --device=/dev/dri -v $(pwd)/data:/app/data rap-rocm
```

#### Slurm (LUMI MI250X)

```bash
sbatch deploy/slurm/lumi_mi250x.slurm
```

### Apple Silicon (M4)

```bash
chmod +x deploy/macos/setup_m4.sh
./deploy/macos/setup_m4.sh
source venv/bin/activate
python3 run_matrix.py
```

### CPU Only (12600K, fallback)

```bash
docker build -f deploy/docker/Dockerfile.cpu -t rap-cpu .
docker run -v $(pwd)/data:/app/data rap-cpu
```

## Output

Results saved to `data/reports/<hardware_type>/`:

- `matrix_results_<timestamp>.csv` - Raw metrics (accuracy, latency, throughput)
- `ieee_table_<timestamp>.tex` - LaTeX table for IEEE TDKE paper
- `full_results_<timestamp>.json` - Complete run data

### Metrics

- **Accuracy**: Field mapping success rate (0.0 - 1.0)
- **Latency**: Per-reconciliation time (ms)
- **Throughput**: Packets processed per second (pps)
- **Total Time**: End-to-end matrix execution time (ms)
- **Batch Size**: GPU batch size for model inference (auto-scaled by VRAM)

## Methodology

### Execution Phases

The matrix executes in **4 sequential phases**, each phase running concurrently within itself:

| Phase | Reconcilers | Combos | Runtime | Notes |
|-------|-------------|--------|---------|-------|
| 1. Fast | Levenshtein, Regex | 24 | ~6s each | CPU-bound, warmup |
| 2. BERT | BERT (MiniLM-v2) | 12 | ~30-60s each | GPU batch encoding |
| 3. Gemma E4B | Gemma4-E4B-it | 12 | ~1-10 min each | LLM-based, GPU |
| 4. Gemma 31B | Gemma4-31b-gguf | 12 | ~2-20 min each | Large LLM, GPU |

**BERT and Gemma never run simultaneously.** Each GPU model type gets exclusive hardware access during its phase with `concurrent_runs` parallel instances.

### Full Combination Matrix (60 Runs)

```
Phase 1: Fast CPU (24 runs)
├── Levenshtein × 12
│   ├── openf1 × (gemma, json_manip, schema_alter)
│   ├── finnhub × (gemma, json_manip, schema_alter)
│   ├── spacex × (gemma, json_manip, schema_alter)
│   └── openmeteo × (gemma, json_manip, schema_alter)
└── Regex × 12 (same structure)

Phase 2: BERT (12 runs)
└── BERT × 12
    ├── openf1 × (gemma, json_manip, schema_alter)
    ├── finnhub × (gemma, json_manip, schema_alter)
    ├── spacex × (gemma, json_manip, schema_alter)
    └── openmeteo × (gemma, json_manip, schema_alter)

Phase 3: Gemma E4B (12 runs)
└── Gemma4-E4B-it × 12 (same structure)

Phase 4: Gemma 31B (12 runs)
└── Gemma4-31b-gguf × 12 (same structure)
```

### Run Criteria

Each combination processes one API source through one chaos method and one reconciler:

| Criterion | Values | Count |
|-----------|--------|-------|
| API Source | OpenF1, Finnhub, SpaceX, OpenMeteo | 4 |
| Chaos Method | Gemma4-e4b-it (LLM drift), JSON manipulation (noise/shuffle/wrap), Schema alteration (coerce/rename/flatten) | 3 |
| Reconciler | Levenshtein (edit distance), Regex (pattern match), BERT (embedding sim), Gemma4-E4B-it (LLM), Gemma4-31b-gguf (LLM) | 5 |
| **Total** | | **60** |

### Hardware Volume

- **100,000 packets** total ingested (25,000 per API)
- **5,000 chaos injections** (5% of packets randomly selected)
- **1,250 drifted packets per combination**
- **100Hz ingestion rate** per source (adaptive throttling)

### Chaos Methods

1. **Gemma4-e4b-it** — LLM-generated semantic drift (field renames, value transformations)
2. **JSON Manipulation** — Noise injection, key shuffling, nested wrapping
3. **Schema Alteration** — Type coercion, field renaming, nested flattening

#### Drift Types

- **Field Split**: `temperature` → `temperature_part1`, `temperature_part2`
- **Field Join**: `speed` + `direction` → `speed_direction`
- **Translation**: `temperature` → `temp_c`
- **Variable Drop**: Random field deletion

### Reconciliation Methods

1. **Levenshtein** — Edit distance fuzzy matching (threshold ≤ 3). Fast, deterministic.
2. **Regex** — Pattern-based semantic matching using predefined field patterns. Fast, deterministic.
3. **BERT (MiniLM-v2)** — Sentence embedding cosine similarity (threshold > 0.7). GPU-accelerated batch encoding.
4. **Gemma4-E4B-it** — 4B parameter LLM for schema field mapping. GPU-accelerated via llama.cpp.
5. **Gemma4-31b-gguf** — 31B parameter quantized LLM for schema field mapping. GPU-accelerated via llama.cpp.

### Hardware Scaling

- GPU compute scaled to VRAM via `VRAMProber` at startup
- BERT and Gemma models use exclusive GPU time in separate phases
- Concurrent runs within each phase = `free_vram_gb / 8`

## Dependencies

### Python

- `torch>=2.1.0` - PyTorch for ML models
- `transformers>=4.36.0` - Hugging Face transformers
- `sentence-transformers>=2.2.2` - BERT embeddings
- `python-Levenshtein>=0.23.0` - Edit distance
- `pynvml>=11.5.0` - NVIDIA GPU monitoring
- `psutil>=5.9.0` - System resource monitoring
- `llama-cpp-python>=0.2.0` - GGUF model inference

### Go

- `gorilla/websocket` - WebSocket client (optional)

## Troubleshooting

### Models Not Found

Ensure `models/download_from_r2.sh` has correct R2 bucket URL and models are downloaded to `models/` directory.

### CUDA Out of Memory

Reduce `concurrent_runs` in `configs/hardware_profiles.json` or let VRAM prober auto-scale.

### ROCm Device Not Detected

Verify `rocm-smi` is installed and GPU is visible: `rocm-smi --showproductname`

### Apple Silicon Low Throughput

M4 uses CPU fallback for some models. Expect 2-3x slower than CUDA.

### Go Ingestion Rate Limited

APIs may throttle at 100Hz. Framework auto-throttles on 429 errors.

## Architecture

```
resilient-data/
├── go/ingestion/          # Go async streaming clients
├── src/
│   ├── chaos/             # Chaos injection engines
│   ├── reconciliation/    # 5 reconciliation methods
│   ├── hardware/          # Detection & VRAM probing
│   ├── orchestration/     # Matrix executor
│   └── telemetry/         # IEEE-formatted logging
├── models/                # GGUF model storage
├── deploy/                # Docker, Slurm, native scripts
├── configs/               # API endpoints, hardware profiles
└── data/                  # Ingestion, chaos logs, results
```

## Batch Size Scaling

The framework automatically scales batch size based on available VRAM:

| VRAM | Batch Size | Target Hardware |
|------|------------|-----------------|
| < 16 GB | 4 | CPU, M4 |
| 16-31 GB | 8 | 7900XT, M4 Pro |
| 32-79 GB | 16 | RTX 5090, RTX 6000 |
| 80-199 GB | 32 | A100, H100, GH200, MI250X |
| ≥ 200 GB | 64 | B300 |

**Benefits**:
- Larger batches = faster GPU inference (especially BERT, Gemma)
- Auto-calculated by `VRAMProber` on startup
- Logged in all output files (CSV, LaTeX, JSON)

## Citation

For IEEE TDKE paper submission, use generated LaTeX tables from `data/reports/<hardware>/ieee_table_*.tex`.

## License

Copyright (c) 2026 Tarek Clarke. All rights reserved.
