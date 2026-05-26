# Semantic Drift Evaluation Pipeline

Cross-platform benchmark for semantic schema drift detection and reconciliation
using BERT embeddings and Gemma-4 E4B, evaluated under controlled chaos injection
on real-world API schemas (Finnhub, OpenMeteo, SpaceX, OpenF1).

## Results

| Metric | Apple M4 (MPS) | AMD RX 7900 XT (ROCm) |
|--------|----------------|----------------------|
| Detection rate (cold) | 1.0 | 0.8859 |
| p95 latency (cold) | 120.0 ms | 4397.92 ms |
| Detection rate (stable) | 1.0 | 0.8856 |
| p95 latency (stable) | 117.0 ms | 4392.39 ms |
| Total runs | 864 | 815 |
| Global runtime | 418.9352 s | 11893.95 s |

### Ablation Study

| Condition | Detection Rate (mean � ci95) | p95 Latency (mean � ci95) | Resilience P (mean � ci95) |
|-----------|------|------|------|
| full_pipeline | 0.8859 � 0.0218 | 4397.92 � 466.40 ms | 0.4639 � 0.0058 |
| ablation_no_bert | 0.8775 � 0.0319 | 4241.14 � 635.30 ms | 0.4309 � 0.0122 |
| ablation_no_gemma | 0.8846 � 0.0307 | 4489.44 � 638.53 ms | 0.4625 � 0.0082 |
| ablation_fast_only | 0.8854 � 0.0305 | 4520.06 � 639.05 ms | 0.4103 � 0.0102 |
| baseline_no_chaos | 0.0000 � 0.0000 | 55.80 � 3.01 ms | 0.2984 � 0.0043 |

## Methodology

- **864 configurations**: 2 packet profiles � 3 frequencies � 3 chaos strategies � 3 levels � 4 APIs, 4 runs each
- **Chaos strategies**: JSON mutation, schema drift, Gemma-generated adversarial mutations
- **Reconcilers**: Levenshtein distance, regex, BERT semantic similarity (all-MiniLM-L6-v2), Gemma-4 E4B
- **Metrics**: Detection rate, p95 latency, repair rate, recovery score, resilience P/P2

## Raw Run Methodology

- **Raw generation mode**: run `python run_all.py --generate-only` to write per-run JSON artifacts.
- **Destination**: artifacts are written to `results/raw/<hardware_token>/`.
- **Cross-platform policy**: keep one hardware token folder per platform (HPC/CUDA, Apple Silicon/MPS, consumer GPU/ROCm or CUDA).
- **Raw filename schema**: `run_{run:03d}_{api}_{packet}_{freq}_{chaos}_{level}_{hardware}_{drift_or_clean}.json`.
- **Baseline filename schema**: `baseline_run_{run:03d}_{api}_{packet}_{freq}_{chaos}_{level}_{hardware}_{drift_or_clean}.json`.
- **Baseline minimum policy**: baseline clean pipeline is topped up to at least 5 runs per baseline config by default (`--min-baseline-runs`).
- **Run-count policy**: standard phases are controlled by `--runs-per-config` and tagged with `policy_tag` metadata.
- **Stable metric policy**: stable means exclude run 1 and summarize runs 2..N.
- **Provenance policy**: each run record carries `policy` + `policy_tag` metadata for reproducibility tracking.
- **Analysis workflow**: analyze each platform independently via `python analyze.py --data-dir results/raw/<hardware_token>`.

## Hardware

| Platform | GPU | Memory | Precision |
|----------|-----|--------|-----------|
| Apple Silicon | M4 (MPS) | Unified | float16 |
| AMD ROCm | RX 7900 XT (gfx1100) | 20 GB | bfloat16 |
