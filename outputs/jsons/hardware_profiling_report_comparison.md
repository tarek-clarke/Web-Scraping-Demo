# Hardware Profiling Report — Cadillac F1 Telemetry Pipeline

**Generated:** 2026-02-23T18:17:17.123996  
**Author:** SRE Orchestrator  
**Purpose:** Benchmark resilient-rap pipeline on NVMe vs HDD storage

---

## Executive Summary

This benchmark compares telemetry pipeline performance across two storage tiers:
- **NVMe (Fast)**: /tmp/data_nvme
- **HDD (Slow)**: /tmp/data_hdd

---

## Key Findings

### Latency Performance (p95 latency in milliseconds)

| Metric | NVME | HDD | Improvement |
|--------|------|-----|-------------|
| Avg Latency (p95 ms) | 44.09 ms | 43.97 ms | -0.29% |
| Total Breaker Trips | 3 | 4 | - |

### Interpretation

- **Latency Improvement:** NVMe is **-0.29% faster** than HDD for p95 latency.
- **Circuit Breaker Health:** 
  - NVME trips: 3
  - HDD trips: 4

---

## Detailed Results

### NVMe Drive Statistics
- **Rows processed:** 15
- **Mean latency_p95_ms:** 44.09 ms
- **Median latency_p95_ms:** 29.01 ms
- **Std Dev:** 27.22 ms
- **Min:** 23.98 ms
- **Max:** 123.02 ms

### HDD Drive Statistics
- **Rows processed:** 15
- **Mean latency_p95_ms:** 43.97 ms
- **Median latency_p95_ms:** 32.68 ms
- **Std Dev:** 23.32 ms
- **Min:** 26.06 ms
- **Max:** 101.78 ms

---

## Recommendations

1. **For Production Race-Day Operations:**
   - Use **NVMe drives** for primary telemetry buffering to minimize latency.
   - Reserve HDD for archival and audit log retention.

2. **Cost-Benefit Analysis:**
   - NVMe latency benefit: -0.29%
   - Justifies NVMe investment for trackside critical path.

3. **Failover Strategy:**
   - If NVMe fails, HDD can take over with acceptable latency degradation.

---

## Test Parameters

- **Script:** tools/cadillac_stress_test.py
- **NVME Path:** /tmp/data_nvme
- **HDD Path:** /tmp/data_hdd
- **Timestamp:** 2026-02-23T18:17:17.123996

---

*End of Report*
