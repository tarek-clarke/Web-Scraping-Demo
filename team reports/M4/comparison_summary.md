# Dual Car Benchmarking Comparison (M4)

This report captures the two-car Apple M4 benchmark run from today. It is the lower CPU-fallback comparator beneath the 7900XT shared-GPU team run.

## Performance Overview

| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **M4** | Total Packets | 30,000 | 60,000 (30k/car) | 2x Load |
| **M4** | Acceptance Rate | 87.12% | 67.18% | Car 1 cleaner load, Car 2 hit one breaker trip |
| **M4** | p95 Latency | 0.020 ms | 0.021 ms | Both remained sub-millisecond |
| **M4** | Circuit Breaker Trips | 0 | 1 | 1 total |
| **M4** | Resilience Score | 0.9992 | 0.9197 | Car 1 stronger overall |
| **M4** | Hardware | Apple M4 | Apple M4 | CPU-fallback two-car run |

### Analysis
- **Concurrency**: Two telemetry pipelines were run in parallel on the same Apple M4 machine.
- **Latency Impact**: p95 latency stayed in the sub-millisecond range for both cars.
- **Reliability**: Car 1 completed without breaker trips; Car 2 tripped once during the Silverstone segment.

### Raw Logs
- [Car 1 run log](run_log_car1_M4_Run2.txt)
- [Car 2 run log](run_log_car2_M4_Run2.txt)
