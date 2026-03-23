# Dual Car Benchmarking Comparison (M4)

This report compares the performance of the two-car Apple M4 sprint and weekend pipelines running concurrently on the same Apple M4 machine.

## Sprint Overview

| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint** | Total Packets | 30,000 | 60,000 (30k/car) | 2x Load |
| **Sprint** | p95 Latency | 0.005 ms | 0.008 ms | Slightly higher, still sub-millisecond |
| **Sprint** | Circuit Breaker Trips | 0 | 0 | Consistent Stability |
| **Both** | Acceptance Rate | 95.81% | 95.71% | Consistent |

### Sprint Latency Impact
- **Latency Impact**: Processing two vehicles concurrently (60,000 packets) on the Apple M4 over the sprint run resulted in a slight latency increase, but p95 latency remained well within the sub-millisecond SLO.

### Sprint Analysis
- **Concurrency**: Two telemetry pipelines were run in parallel on the same Apple M4 machine.
- **Latency Impact**: The overhead of processing two vehicles concurrently on the same hardware resulted in a small latency increase, but the p95 latency remained well within the sub-millisecond SLO.
- **Reliability**: Acceptance rates and chaotic recovery behaved consistently. There were no circuit breaker trips in either run.

### Sprint Accompanying Raw Data
- [Car 1 run log](run_log_SprintTeam_Car1_M4.txt)
- [Car 2 run log](run_log_SprintTeam_Car2_M4.txt)

## Weekend Overview

| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **Weekend** | Total Packets | 3,600,000 | 7,200,000 (3.6M/car) | 2x Extreme Load |
| **Weekend** | p95 Latency | 0.003 ms | 0.003 ms | No measurable overhead |
| **Weekend** | Circuit Breaker Trips | 0 | 0 | Consistent Stability |
| **Both** | Acceptance Rate | 95.75% | 95.67% | Consistent |

### Weekend Latency Impact
- **Latency Impact**: Processing two vehicles concurrently (7.2 million packets) on the Apple M4 over the weekend run resulted in a trivial latency increase, and p95 latency remained well within the sub-millisecond SLO.

### Weekend Analysis
- **Concurrency**: Two telemetry pipelines were run in parallel on the same Apple M4 machine.
- **Latency Impact**: The overhead of processing two vehicles concurrently on the same hardware resulted in a trivial increase, but p95 latency remained well within the sub-millisecond SLO.
- **Reliability**: Acceptance rates and chaotic recovery behaved consistently. There were no circuit breaker trips in either run.

### Weekend Accompanying Raw Data
- [Car 1 run log](run_log_M4Team_Car1.txt)
- [Car 2 run log](run_log_M4Team_Car2.txt)
