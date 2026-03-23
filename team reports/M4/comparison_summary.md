# Dual Car Benchmarking Comparison (M4)

This report captures the two-car Apple M4 weekend team run from today. It is the lower CPU-fallback comparator beneath the 7900XT shared-GPU team run.

## Performance Overview

| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **Weekend** | Total Packets | 3,600,000 | 7,200,000 (3.6M/car) | 2x Extreme Load |
| **Weekend** | p95 Latency | 0.003 ms | 0.003 ms | No measurable overhead |
| **Weekend** | Circuit Breaker Trips | 0 | 0 | Consistent Stability |
| **Both** | Acceptance Rate | 95.75% | 95.76% | Consistent |
| **Both** | Resilience Score | 0.9995 | 0.9995 | Consistent |
| **Both** | Hardware | Apple M4 | Apple M4 | CPU-fallback team run |

### Analysis
- **Concurrency**: Two telemetry pipelines were run in parallel on the same Apple M4 machine.
- **Load**: The weekend run processed 3.6 million packets per car, for 7.2 million combined.
- **Latency Impact**: p95 latency stayed in the sub-millisecond range for both cars.
- **Reliability**: Neither car tripped the circuit breaker during the weekend run.

### Raw Logs
- [Car 1 run log](run_log_M4Team_Car1.txt)
- [Car 2 run log](run_log_M4Team_Car2.txt)
