# Dual Car Benchmarking Comparison (M4)

This report compares the performance of the two-car Apple M4 sprint and weekend pipelines running concurrently on the same Apple M4 machine.

| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint** | Total Packets | 30,000 | 60,000 (30k/car) | 2x Load |
| **Sprint** | p95 Latency | 0.005 ms | 0.008 ms | Slightly higher, still sub-millisecond |
| **Sprint** | Circuit Breaker Trips | 0 | 0 | Consistent Stability |
| **Weekend** | Total Packets | 3,600,000 | 7,200,000 (3.6M/car) | 2x Extreme Load |
| **Weekend** | p95 Latency | 0.003 ms | 0.003 ms | No measurable overhead |
| **Weekend** | Circuit Breaker Trips | 0 | 0 | Consistent Stability |
| **Both** | Acceptance Rate | 95.81% / 95.75% | 95.71% / 95.67% | Consistent |

### Latency Impact
- **Latency Impact**: Processing two vehicles concurrently on the Apple M4 remained well within the sub-millisecond SLO across both sprint and weekend runs.

### Analysis
- **Concurrency**: Two telemetry pipelines were run in parallel on the same Apple M4 machine.
- **Reliability**: Acceptance rates and chaotic recovery behaved consistently. There were no circuit breaker trips in either run.

### Accompanying Raw Data
- [Sprint car 1 run log](run_log_SprintTeam_Car1_M4.txt)
- [Sprint car 2 run log](run_log_SprintTeam_Car2_M4.txt)
- [Weekend car 1 run log](run_log_M4Team_Car1.txt)
- [Weekend car 2 run log](run_log_M4Team_Car2.txt)
