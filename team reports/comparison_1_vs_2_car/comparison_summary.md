# Dual Car Benchmarking Comparison (7900XT)

This report compares the performance of the standard 1-car telemetry pipeline against the 2-car (Team) telemetry pipeline running concurrently on the same AMD Radeon RX 7900 XT GPU.

## Performance Overview

| Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- |
| **Total Packets** | 2,000 | 4,000 (2,000 per car) | 2x Load |
| **p95 Latency** | 0.007 ms | ~0.010 ms | +0.003 ms overhead |
| **Circuit Breaker Trips** | 0 | 0 | Consistent Stability |
| **Acceptance Rate**| 99.97% | 99.97% | Consistent Stability |
| **Hardware** | 7900XT | 7900XT | Shared GPU Resources |

### Analysis
- **Concurrency**: The Dual Car run utilized two parallel instances of the pipeline, heavily pushing the batching capabilities of the GPU.
- **Latency Impact**: The overhead of processing two vehicles concurrently on the same hardware resulted in a trivial latency increase of roughly 3 microseconds (0.003 ms). The p95 latency remained well within the sub-millisecond SLO.
- **Reliability**: Acceptance rates and chaotic recovery behaved identically. There were no circuit breaker trips in either run.

### Accompanying Raw Data
The raw JSON and CSV reports for these specific runs have been copied into this folder for deeper inspection:
- `...sprint_7900XT_Run2.json/csv` (1-Car Baseline)
- `...team_car1_7900XT.json/csv` (Car 1 of Team Run)
- `...team_car2_7900XT.json/csv` (Car 2 of Team Run)
