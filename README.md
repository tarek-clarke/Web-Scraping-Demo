# Semantic Drift Evaluation Pipeline

Cross-platform benchmark for semantic schema drift detection and reconciliation
using BERT embeddings and Gemma-4 E4B, evaluated under controlled chaos injection
on real-world API schemas (Finnhub, OpenMeteo, SpaceX, OpenF1).

## Results

Raw results summary from `results/raw`:

Average metrics computed across raw per-run JSONs.

**Table: Average of runs 1–5 (inclusive)**

| Platform | Runs | Avg p95 Latency (ms) | Detection Rate | Avg Recovery Score | Avg Resilience P | Avg Throughput (pps) |
|--------|----|--------------------|--------------|------------------|----------------|--------------------|
| AMD_Radeon_RX_7900_XT_20GB | 5 | 546.990 | 0.862 | 0.981 | 0.443 | 9.555 |
| Apple M4 16GB | 5 | 208.127 | 0.884 | 0.981 | 0.433 | 4.858 |
| GH200 | 5 | 7.679 | 0.892 | 0.977 | 0.736 | 197.682 |
| NVIDIA_B200_178GB | 5 | 34.033 | 0.896 | 0.980 | 0.538 | 36.946 |
| NVIDIA_B300_SXM6_AC_268GB | 5 | 25.935 | 0.869 | 0.982 | 0.584 | 51.283 |
| NVIDIA_GeForce_RTX_5090 | 5 | 24.101 | 0.881 | 0.977 | 0.643 | 116.374 |
| NVIDIA_H100_80GB_HBM3_79GB | 5 | 14.237 | 0.890 | 0.978 | 0.715 | 180.211 |
| NVIDIA_H200_140GB | 5 | 8.554 | 0.894 | 0.978 | 0.732 | 165.231 |
| RTX 6000 Workstation | 5 | 35.837 | 0.875 | 0.977 | 0.596 | 65.006 |

**Table: Average of runs 2–5 (drop run 1 to reduce cold-start effects)**

| Platform | Runs | Avg p95 Latency (ms) | Detection Rate | Avg Recovery Score | Avg Resilience P | Avg Throughput (pps) |
|--------|----|--------------------|--------------|------------------|----------------|--------------------|
| AMD_Radeon_RX_7900_XT_20GB | 5 | 545.515 | 0.855 | 0.981 | 0.442 | 9.576 |
| Apple M4 16GB | 5 | 207.640 | 0.888 | 0.981 | 0.434 | 4.867 |
| GH200 | 5 | 7.683 | 0.899 | 0.977 | 0.738 | 197.324 |
| NVIDIA_B200_178GB | 5 | 33.285 | 0.894 | 0.980 | 0.538 | 36.975 |
| NVIDIA_B300_SXM6_AC_268GB | 5 | 19.956 | 0.872 | 0.982 | 0.584 | 51.290 |
| NVIDIA_GeForce_RTX_5090 | 5 | 24.213 | 0.872 | 0.977 | 0.641 | 115.264 |
| NVIDIA_H100_80GB_HBM3_79GB | 5 | 14.418 | 0.889 | 0.977 | 0.714 | 178.743 |
| NVIDIA_H200_140GB | 5 | 8.562 | 0.899 | 0.978 | 0.734 | 164.839 |
| RTX 6000 Workstation | 5 | 35.881 | 0.870 | 0.977 | 0.595 | 64.777 |

### Ablation Study

Full-pipeline sweep across all hardware targets:

| Hardware | Runs | Detection Rate (mean ± ci95) | p95 Latency (mean ± ci95) | Resilience P (mean ± ci95) |
|----------|------|------------------------------|---------------------------|----------------------------|
| AMD RX 7900 XT (Windows) | 1080 | 0.8620 ± 0.0264 | 546.99 ± 2.91 ms | 0.4433 ± 0.0061 |
| Apple M4 16GB | 1080 | 0.8843 ± 0.0191 | 208.13 ± 1.34 ms | 0.4333 ± 0.0047 |
| GH200 | 1080 | 0.8917 ± 0.0185 | 7.68 ± 0.26 ms | 0.7357 ± 0.0101 |
| NVIDIA B200 178GB | 1080 | 0.8963 ± 0.0110 | 34.03 ± 2.26 ms | 0.5385 ± 0.0022 |
| NVIDIA B300 268GB | 1080 | 0.8694 ± 0.0201 | 25.94 ± 11.75 ms | 0.5836 ± 0.0071 |
| NVIDIA GeForce RTX 5090 | 1080 | 0.8806 ± 0.0194 | 24.10 ± 1.43 ms | 0.6430 ± 0.0110 |
| NVIDIA H100 80GB HBM3 79GB | 1080 | 0.8898 ± 0.0173 | 14.24 ± 0.87 ms | 0.7148 ± 0.0040 |
| NVIDIA H200 140GB | 1080 | 0.8935 ± 0.0184 | 8.55 ± 0.25 ms | 0.7321 ± 0.0105 |
| RTX 6000 Workstation | 1080 | 0.8750 ± 0.0197 | 35.84 ± 1.88 ms | 0.5961 ± 0.0105 |

### Chaos-Method Ablation Matrix

Means computed directly from the raw per-run JSONs in `results/raw`.
Each cell is the mean across 360 runs for that hardware/chaos-method pair.

**Detection Rate**

| Hardware | JSON mutation | Schema drift | Gemma adversarial |
|----------|--------------:|-------------:|------------------:|
| AMD RX 7900 XT (Windows) | 0.9639 | 0.6750 | 0.9472 |
| Apple M4 16GB | 0.9528 | 0.7306 | 0.9694 |
| GH200 | 0.9583 | 0.7472 | 0.9694 |
| NVIDIA B200 178GB | 0.9694 | 0.7528 | 0.9667 |
| NVIDIA B300 268GB | 0.9639 | 0.6972 | 0.9472 |
| NVIDIA GeForce RTX 5090 | 0.9639 | 0.7222 | 0.9556 |
| NVIDIA H100 80GB HBM3 79GB | 0.9778 | 0.7278 | 0.9639 |
| NVIDIA H200 140GB | 0.9472 | 0.7583 | 0.9750 |
| RTX 6000 Workstation | 0.9667 | 0.7056 | 0.9528 |

**p95 Latency (ms)**

| Hardware | JSON mutation | Schema drift | Gemma adversarial |
|----------|--------------:|-------------:|------------------:|
| AMD RX 7900 XT (Windows) | 75.43 | 71.69 | 1493.85 |
| Apple M4 16GB | 209.00 | 207.37 | 208.02 |
| GH200 | 4.79 | 5.07 | 13.18 |
| NVIDIA B200 178GB | 46.40 | 24.60 | 31.10 |
| NVIDIA B300 268GB | 35.86 | 18.03 | 23.91 |
| NVIDIA GeForce RTX 5090 | 8.66 | 9.32 | 54.33 |
| NVIDIA H100 80GB HBM3 79GB | 10.67 | 12.60 | 19.44 |
| NVIDIA H200 140GB | 5.98 | 6.40 | 13.29 |
| RTX 6000 Workstation | 13.60 | 14.37 | 79.54 |

**Resilience P**

| Hardware | JSON mutation | Schema drift | Gemma adversarial |
|----------|--------------:|-------------:|------------------:|
| AMD RX 7900 XT (Windows) | 0.4833 | 0.4125 | 0.4343 |
| Apple M4 16GB | 0.4502 | 0.3958 | 0.4538 |
| GH200 | 0.7804 | 0.7267 | 0.7000 |
| NVIDIA B200 178GB | 0.5477 | 0.5240 | 0.5436 |
| NVIDIA B300 268GB | 0.6230 | 0.5566 | 0.5711 |
| NVIDIA GeForce RTX 5090 | 0.7432 | 0.6815 | 0.5043 |
| NVIDIA H100 80GB HBM3 79GB | 0.7607 | 0.6848 | 0.6990 |
| NVIDIA H200 140GB | 0.7723 | 0.7238 | 0.7003 |
| RTX 6000 Workstation | 0.6918 | 0.6213 | 0.4753 |

**Best Method by Hardware**

| Hardware | Best Detection Rate | Lowest p95 Latency | Best Resilience P |
|----------|--------------------|-------------------|------------------|
| AMD RX 7900 XT (Windows) | JSON mutation | Schema drift | JSON mutation |
| Apple M4 16GB | Gemma adversarial | Schema drift | Gemma adversarial |
| GH200 | Gemma adversarial | JSON mutation | JSON mutation |
| NVIDIA B200 178GB | JSON mutation | Schema drift | JSON mutation |
| NVIDIA B300 268GB | JSON mutation | Schema drift | JSON mutation |
| NVIDIA GeForce RTX 5090 | JSON mutation | JSON mutation | JSON mutation |
| NVIDIA H100 80GB HBM3 79GB | JSON mutation | JSON mutation | JSON mutation |
| NVIDIA H200 140GB | Gemma adversarial | JSON mutation | JSON mutation |
| RTX 6000 Workstation | JSON mutation | JSON mutation | JSON mutation |


## Methodology

- **216 configurations / 1080 total runs**: 2 packet profiles × 3 frequencies × 3 chaos strategies × 3 levels × 4 APIs, 5 runs each
- **Chaos strategies**: JSON mutation, schema drift, Gemma-generated adversarial mutations
- **Reconcilers**: Levenshtein distance, regex, BERT semantic similarity (all-MiniLM-L6-v2), Gemma-4 E4B
- **Metrics**: Detection rate, p95 latency, repair rate, recovery score, resilience P/P2


## Cloud Instance Setup

- **AMD RX 7900 XT**: Windows-based workstation with 20 GB VRAM — on-premise ROCm evaluation
- **GH200**: NVIDIA Grace Hopper (native, 141 GB HBM3) — on-premise evaluation node
- **NVIDIA B200 178GB**: NVIDIA Blackwell datacenter node — on-premise evaluation node
- **NVIDIA B300 268GB**: NVIDIA Blackwell datacenter node — on-premise evaluation node
- **NVIDIA H100 80GB HBM3 79GB**: NVIDIA Hopper datacenter node — on-premise evaluation node
- **NVIDIA H200 140GB**: NVIDIA Hopper datacenter node — on-premise evaluation node
- **NVIDIA RTX 5090**: Standalone workstation — on-premise evaluation node
- **RTX 6000 Workstation**: Vast.ai GPU marketplace — remote instance provisioning
- **Apple M4**: MacBook Pro (native Metal Performance Shaders) — on-premise evaluation
