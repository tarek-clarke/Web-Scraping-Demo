# Semantic Drift Evaluation Pipeline

Cross-platform benchmark for semantic schema drift detection and reconciliation
using BERT embeddings and Gemma-4 E4B, evaluated under controlled chaos injection
on real-world API schemas (Finnhub, OpenMeteo, SpaceX, OpenF1).

## Results

| Metric | Apple M4 (MPS) | AMD RX 7900 XT (ROCm) |
|--------|----------------|----------------------|

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
