# IEEE Data Engineering Submission Pack: Resilient RAP Framework

This document serves as the formal technical appendix for the submission to IEEE Data Engineering, providing absolute clarity on the experimental testbed, methodologies, and raw results for reproducibility.

## 1. Hardware Testbed Specifications

| Target Identifier | Architecture | Memory | Driver/Runtime |
| :--- | :--- | :--- | :--- |
| **NVIDIA B200** | Blackwell | 192GB HBM3e | CUDA 12.6 + TensorRT |
| **NVIDIA H200** | Hopper | 141GB HBM3e | CUDA 12.4 |
| **AMD 7900XT** | RDNA 3 | 20GB GDDR6 | ROCm 6.1 (Windows/HIP) |
| **Apple M4** | Apple Silicon | 32GB Unified | MPS (Metal Performance Shaders) |
| **Intel 12600K** | Alder Lake | 64GB DDR5 | x86 Native Fallback |

## 2. Experimental Methodology

### Data Generation (F1 Synthetic Stream)
*   **Frequency:** 50 Hz (20ms periodicity).
*   **Payload:** High-velocity telemetry (Speed, RPM, Throttle, Brake, Temps, Hybrid Deployment).
*   **Tamper-Evidence:** SHA-256 hash chaining on each packet.

### Chaos Injection (The Resilience Test)
The framework is subjected to **5.0% injected chaos** per session:
*   **Bit Flips:** Low-order and high-order bit inversions in numeric fields.
*   **Schema Drift:** Semantic variations (e.g., `oil_temp` -> `lubricant_thermal_K`).
*   **Type Mismatch:** String-in-numeric corruption.
*   **Sensor Dropout:** Null/NaN injection at irregular intervals.

## 3. Consolidated Results (7900XT Concurrency Validation)

After **3 independent sets** of two-car concurrent runs (7.2M packets/run), the following means were achieved:

| Profile | Packets / Car | Car 1 (Mean) | Car 2 (Mean) | Overall Mean |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint** | 30,000 | 95.71% | 95.69% | **95.70%** |
| **Weekend**| 3,600,000 | 95.41% | 95.74% | **95.58%** |

*   **Concurrency Delta:** Only 0.12% degradation in mean acceptance when scaling from burst load (Sprint) to full race weekend load (Weekend).
*   **P95 Latency Floor:** Maintained at **< 0.010 ms** across all platforms.

## 4. Reproducibility Guide

To reproduce these results, execute the following commands in the root directory:

```bash
# 1-Car Performance Baseline
./tools/run_all_benchmarks.sh

# 2-Car Concurrency Benchmark (as reported in Section 3)
powershell -ExecutionPolicy Bypass -File tools/run_team_test_win.ps1 240000 0.05
```

Reports are automatically generated in `data/reports/` and can be aggregated using:
`python3 tools/aggregate_benchmark_runs.py --dir data/reports/7900XT --platform 7900XT`
