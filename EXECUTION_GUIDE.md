# Resilient RAP Framework - Execution Guide

## Pre-Flight Checklist

### 1. Install Dependencies

```bash
# Python
pip install -r requirements.txt

# Go (if not installed)
# macOS: brew install go
# Ubuntu: sudo apt install golang-go
# Windows: choco install golang
```

### 2. Download Models

Edit `models/download_from_r2.sh` with your Cloudflare R2 bucket URL:

```bash
R2_BUCKET="https://your-bucket.r2.cloudflarestorage.com"
```

Then run:

```bash
./models/download_from_r2.sh
```

Expected files in `models/`:
- `gemma4-e4b-it.gguf` (~4 GB)
- `gemma4-31b-gguf.gguf` (~18 GB quantized)

### 3. Verify Hardware Detection

```bash
python3 validate.py
```

Should output detected hardware type and VRAM.

## Execution Steps

### Step 1: Ingestion (Go)

Streams 100k packets from 4 APIs at 100Hz.

```bash
cd go/ingestion
go mod download
go run main.go
```

**Output**: `data/ingested/telemetry_<timestamp>.json`

**Expected duration**: ~17 minutes (100k packets / 100Hz / 4 sources)

**Rename for matrix**:
```bash
cp data/ingested/telemetry_<timestamp>.json data/ingested/telemetry_latest.json
```

### Step 2: Matrix Execution (Python)

Runs 60 combinations: 4 APIs × 3 chaos methods × 5 reconcilers.

```bash
python3 run_matrix.py
```

**Output**: `data/reports/<hardware_type>/`
- `matrix_results_<timestamp>.csv`
- `ieee_table_<timestamp>.tex`
- `full_results_<timestamp>.json`

**Expected duration**: 30-120 minutes (depends on hardware)

## Hardware-Specific Notes

### Apple M4 (Current System)

- **Type**: Silicon
- **VRAM**: 16 GB (shared memory)
- **Concurrent Runs**: 3
- **Performance**: 2-3x slower than CUDA
- **Models**: CPU fallback for GGUF inference

### NVIDIA CUDA (H100, A100, RTX 5090, etc.)

- **Type**: CUDA
- **VRAM**: 32-288 GB
- **Concurrent Runs**: 3-20 (auto-scaled by VRAM prober)
- **Performance**: Fastest
- **Models**: Full GPU acceleration

### AMD ROCm (7900XT, MI250X)

- **Type**: ROCm
- **VRAM**: 20-128 GB
- **Concurrent Runs**: 2-12
- **Performance**: Comparable to CUDA
- **Models**: GPU acceleration via ROCm

### CPU Only (12600K, fallback)

- **Type**: CPU
- **VRAM**: 0 GB
- **Concurrent Runs**: 4
- **Performance**: Slowest (10-20x vs CUDA)
- **Models**: CPU-only inference

## Troubleshooting

### "No module named 'Levenshtein'"

```bash
pip install python-Levenshtein
```

### "No module named 'torch'"

```bash
pip install torch
```

### CUDA Out of Memory

Reduce concurrent runs in `configs/hardware_profiles.json`:

```json
{
  "RTX5090": {"vram_gb": 32, "type": "cuda", "concurrent_runs": 2}
}
```

### Go Ingestion Fails

Check API availability:

```bash
curl https://api.openf1.org/v1/car_data?session_key=latest
curl https://finnhub.io/api/v1/quote?symbol=AAPL
curl https://api.spacexdata.com/v4/launches/latest
curl https://api.open-meteo.com/v1/forecast?latitude=59.4370&longitude=24.7536&current_weather=true
```

### Models Not Found

Verify models exist in `models/` directory:

```bash
ls -lh models/*.gguf
```

## Output Interpretation

### CSV Format

```csv
api,chaos_method,reconciler,accuracy,avg_latency_ms,total_time_ms,throughput_pps,packets_processed
openf1,gemma,levenshtein,0.847,12.34,45678.90,547.32,25000
```

### LaTeX Table

```latex
\begin{table}[htbp]
\caption{Resilience Matrix Results - cuda}
\begin{tabular}{l l l r r r r}
\hline
API & Chaos & Reconciler & Accuracy & Latency (ms) & Time (ms) & Throughput (pps) \\
\hline
openf1 & gemma & levenshtein & 0.847 & 12.34 & 45678.90 & 547 \\
...
\end{tabular}
\end{table}
```

### Metrics

- **Accuracy**: 0.0 (no fields mapped) to 1.0 (all fields mapped)
- **Latency**: Time per reconciliation call (ms)
- **Throughput**: Packets processed per second (pps)
- **Total Time**: End-to-end matrix execution time (ms)
- **Batch Size**: GPU batch size for model inference (auto-scaled by VRAM)

## Expected Results

### Batch Size Scaling

| Hardware | VRAM | Batch Size | Speedup vs Batch=4 |
|----------|------|------------|-------------------|
| M4 | 16 GB | 8 | 1.5x |
| RTX 5090 | 32 GB | 16 | 2.5x |
| A100 | 80 GB | 32 | 4.0x |
| H100 | 80 GB | 32 | 4.5x |
| GH200 | 96 GB | 32 | 5.0x |
| B300 | 288 GB | 64 | 8.0x |

**Note**: Batch size scaling primarily affects BERT and Gemma model inference. Levenshtein and Regex are CPU-bound.

### Accuracy by Reconciler

| Reconciler | Expected Accuracy | Notes |
|------------|-------------------|-------|
| Levenshtein | 0.6-0.8 | Good for simple field renames |
| Regex | 0.7-0.9 | Best for semantic patterns |
| BERT | 0.8-0.95 | Best for semantic similarity |
| Gemma4-E4B | 0.7-0.9 | LLM-based, fast |
| Gemma4-31B | 0.85-0.98 | LLM-based, slow but accurate |

### Performance by Hardware

| Hardware | Batch Size | Expected Throughput | Notes |
|----------|------------|---------------------|-------|
| M4 | 8 | 50-100 pps | CPU fallback |
| RTX 5090 | 16 | 200-400 pps | GPU acceleration |
| A100 | 32 | 300-500 pps | High VRAM + batch |
| H100 | 32 | 400-600 pps | Fastest |
| GH200 | 32 | 450-650 pps | H100 + ARM |
| B300 | 64 | 500-700 pps | Massive batch |
| MI250X | 32 | 350-550 pps | ROCm optimized |

## Next Steps

1. Run ingestion on target hardware
2. Execute matrix
3. Collect results from `data/reports/<hardware>/`
4. Aggregate across platforms for IEEE TDKE paper
5. Use `src/telemetry/ieee_formatter.py` for cross-platform comparison tables

## Support

For issues, check:
- `data/chaos_log/chaos_events.json` - All chaos injection events
- `data/reports/<hardware>/full_results_*.json` - Complete run logs
- Hardware detection output from `validate.py`
