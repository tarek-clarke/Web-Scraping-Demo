# Dual Car Benchmarking Comparison (M4)

This report captures the two-car Apple M4 sprint and weekend team runs from today. It is the lower CPU-fallback comparator beneath the 7900XT shared-GPU team run.

## Sprint Overview

| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint** | Total Packets | 30,000 | 60,000 (30k/car) | 2x Load |
| **Sprint** | p95 Latency | 0.005 ms | 0.008 ms | Slightly higher, still sub-millisecond |
| **Sprint** | Circuit Breaker Trips | 0 | 0 | Consistent Stability |
| **Sprint** | Acceptance Rate | 95.81% | 95.71% | Consistent |
| **Sprint** | Hardware | Apple M4 | Apple M4 | CPU-fallback team run |

### Sprint Analysis
- **Concurrency**: Two telemetry pipelines were run in parallel on the same Apple M4 machine.
- **Load**: The sprint run processed 30,000 packets per car, for 60,000 combined.
- **Latency Impact**: p95 latency stayed in the sub-millisecond range for both cars.
- **Reliability**: Neither car tripped the circuit breaker during the sprint run.

### Sprint Raw Logs
- [Car 1 run log](run_log_SprintTeam_Car1_M4.txt)
- [Car 2 run log](run_log_SprintTeam_Car2_M4.txt)

## Weekend Overview

| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **Weekend** | Total Packets | 3,600,000 | 7,200,000 (3.6M/car) | 2x Extreme Load |
| **Weekend** | p95 Latency | 0.003 ms | 0.003 ms | No measurable overhead |
| **Weekend** | Circuit Breaker Trips | 0 | 0 | Consistent Stability |
| **Weekend** | Acceptance Rate | 95.75% | 95.67% | Consistent |
| **Weekend** | Hardware | Apple M4 | Apple M4 | CPU-fallback team run |

### Weekend Analysis
- **Concurrency**: Two telemetry pipelines were run in parallel on the same Apple M4 machine.
- **Load**: The weekend run processed 3.6 million packets per car, for 7.2 million combined.
- **Latency Impact**: p95 latency stayed in the sub-millisecond range for both cars.
- **Reliability**: Neither car tripped the circuit breaker during the weekend run.

### Weekend Raw Logs
- [Car 1 run log](run_log_M4Team_Car1.txt)
- [Car 2 run log](run_log_M4Team_Car2.txt)
