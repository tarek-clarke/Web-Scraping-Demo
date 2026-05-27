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
| Apple M4 16GB | 5 | 208.127 | 0.884 | 0.981 | 0.433 | 4.858 |
| GH200 | 5 | 7.679 | 0.892 | 0.977 | 0.736 | 197.682 |
| NVIDIA_B300_SXM6_AC_268GB | 5 | 25.935 | 0.869 | 0.982 | 0.584 | 51.283 |
| NVIDIA_GeForce_RTX_5090 | 5 | 24.101 | 0.881 | 0.977 | 0.643 | 116.374 |
| NVIDIA_H200_140GB | 5 | 8.554 | 0.894 | 0.978 | 0.732 | 165.231 |
| RTX 6000 Workstation | 5 | 35.837 | 0.875 | 0.977 | 0.596 | 65.006 |

**Table: Average of runs 2–5 (drop run 1 to reduce cold-start effects)**

| Platform | Runs | Avg p95 Latency (ms) | Detection Rate | Avg Recovery Score | Avg Resilience P | Avg Throughput (pps) |
|--------|----|--------------------|--------------|------------------|----------------|--------------------|
| Apple M4 16GB | 5 | 207.640 | 0.888 | 0.981 | 0.434 | 4.867 |
| GH200 | 5 | 7.683 | 0.899 | 0.977 | 0.738 | 197.324 |
| NVIDIA_B300_SXM6_AC_268GB | 5 | 19.956 | 0.872 | 0.982 | 0.584 | 51.290 |
| NVIDIA_GeForce_RTX_5090 | 5 | 24.213 | 0.872 | 0.977 | 0.641 | 115.264 |
| NVIDIA_H200_140GB | 5 | 8.562 | 0.899 | 0.978 | 0.734 | 164.839 |
| RTX 6000 Workstation | 5 | 35.881 | 0.870 | 0.977 | 0.595 | 64.777 |

### Ablation Study

Full-pipeline sweep across all hardware targets:

| Hardware | Runs | Detection Rate (mean ± ci95) | p95 Latency (mean ± ci95) | Resilience P (mean ± ci95) |
|----------|------|------------------------------|---------------------------|----------------------------|
| AMD RX 7900 XT (Windows) | 864 | 0.8843 ± 0.0213 | 10729.03 ± 333.51 ms | 0.4172 ± 0.0053 |
| Apple M4 16GB | 1080 | 0.8843 ± 0.0191 | 208.13 ± 1.34 ms | 0.4333 ± 0.0047 |
| GH200 | 1080 | 0.8917 ± 0.0185 | 7.68 ± 0.26 ms | 0.7357 ± 0.0101 |
| NVIDIA B300 268GB | 1080 | 0.8694 ± 0.0201 | 25.94 ± 11.75 ms | 0.5836 ± 0.0071 |
| NVIDIA GeForce RTX 5090 | 1080 | 0.8806 ± 0.0194 | 24.10 ± 1.43 ms | 0.6430 ± 0.0110 |
| NVIDIA H200 140GB | 1080 | 0.8935 ± 0.0184 | 8.55 ± 0.25 ms | 0.7321 ± 0.0105 |
| RTX 6000 Workstation | 1080 | 0.8750 ± 0.0197 | 35.84 ± 1.88 ms | 0.5961 ± 0.0105 |


## Methodology

- **216 configurations / 1080 total runs**: 2 packet profiles × 3 frequencies × 3 chaos strategies × 3 levels × 4 APIs, 5 runs each
- **Chaos strategies**: JSON mutation, schema drift, Gemma-generated adversarial mutations
- **Reconcilers**: Levenshtein distance, regex, BERT semantic similarity (all-MiniLM-L6-v2), Gemma-4 E4B
- **Metrics**: Detection rate, p95 latency, repair rate, recovery score, resilience P/P2


## Cloud Instance Setup

- **GH200**: NVIDIA Grace Hopper (native, 141 GB HBM3) — on-premise evaluation node
- **NVIDIA B300 268GB**: NVIDIA Blackwell datacenter node — on-premise evaluation node
- **NVIDIA H200 140GB**: NVIDIA Hopper datacenter node — on-premise evaluation node
- **NVIDIA RTX 5090**: Standalone workstation — on-premise evaluation node
- **RTX 6000 Workstation**: Vast.ai GPU marketplace — remote instance provisioning
- **AMD RX 7900 XT**: Windows-based workstation — on-premise ROCm evaluation
- **Apple M4**: MacBook Pro (native Metal Performance Shaders) — on-premise evaluation
