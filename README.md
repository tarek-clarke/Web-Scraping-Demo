# Semantic Drift Evaluation Pipeline

Cross-platform benchmark for semantic schema drift detection and reconciliation
using BERT embeddings and Gemma-4 E4B, evaluated under controlled chaos injection
on real-world API schemas (Finnhub, OpenMeteo, SpaceX, OpenF1).

## Results

Raw results summary from `results/raw`:

| Platform | Runs | Avg p95 Latency (ms) | Detection Rate | Avg Recovery Score | Avg Resilience P | Avg Throughput (pps) |
|----------|------|----------------------|----------------|--------------------|------------------|----------------------|
| AMD RX 7900 XT (Windows) | 864 | 10729.033 | 0.884 | 0.979 | 0.417 | 0.111 |
| Apple M4 16GB | 1100 | 207.984 | 0.868 | 0.982 | 0.430 | 4.862 |
| GH200 | 1100 | 7.693 | 0.875 | 0.978 | 0.736 | 196.250 |
| NVIDIA GeForce RTX 5090 | 1100 | 23.877 | 0.865 | 0.977 | 0.643 | 115.974 |
| RTX 6000 Workstation | 1100 | 35.623 | 0.859 | 0.977 | 0.593 | 64.580 |

### Ablation Study

| Condition | Detection Rate (mean ± ci95) | p95 Latency (mean ± ci95) | Resilience P (mean ± ci95) |
|-----------|------|------|------|
| FULL | 0.8750 ± 0.0197 | 35.84 ± 1.88 ms | 0.5961 ± 0.0105 |

## Methodology

- **864 configurations**: 2 packet profiles × 3 frequencies × 3 chaos strategies × 3 levels × 4 APIs, 4 runs each
- **Chaos strategies**: JSON mutation, schema drift, Gemma-generated adversarial mutations
- **Reconcilers**: Levenshtein distance, regex, BERT semantic similarity (all-MiniLM-L6-v2), Gemma-4 E4B
- **Metrics**: Detection rate, p95 latency, repair rate, recovery score, resilience P/P2

## Hardware

| Platform | GPU | Memory | Precision |
|----------|-----|--------|-----------|
| Apple Silicon | M4 (MPS) | Unified | float16 |
| AMD ROCm | RX 7900 XT (gfx1100) | 20 GB | bfloat16 |
| NVIDIA CUDA | RTX 6000 Workstation | 48 GB | float16 |
