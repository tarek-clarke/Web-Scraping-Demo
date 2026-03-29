# Walkthrough: Resilient RAP Framework Setup & High-Frequency Validation

We have successfully cloned the Resilient RAP framework and verified its performance at 1kHz and 1MHz frequencies on Apple M4 hardware.

## 1. Repository Cloning
The repository was cloned into a fresh environment to ensure a clean slate for production research.
- **Path**: `/Users/tarekclarke/Resilient RAP/resilient-rap-framework-fresh`

## 2. High-Frequency Support
The `telemetry_gpu_stress_test.py` utility now supports a `--frequency` argument for precise aggregate telemetry rate control.

## 3. Performance Results (Apple M4)
The framework maintains sub-millisecond p95 latency even under extreme 1MHz synthetic load.

| Profile | Frequency | p95 Latency | Resilience | Artifacts (M4) |
| :--- | :--- | :--- | :--- | :--- |
| **1kHz Standard** | 1,000 Hz | 0.012 ms | 99.70% | [Report](file:///Users/tarekclarke/Resilient RAP/resilient-rap-framework/data/reports/M4/telemetry_gpu_stress_test_report_1000hz_M4.json) |
| **1kHz Weekend** | 1,000 Hz | **0.0048 ms** | 99.71% | [Report](file:///Users/tarekclarke/Resilient RAP/resilient-rap-framework/data/reports/M4/telemetry_gpu_stress_test_report_weekend_1000hz_3.6m_M4.json) |
| **1MHz Standard** | 1,000,000 Hz | 0.011 ms | 99.59% | [Report](file:///Users/tarekclarke/Resilient RAP/resilient-rap-framework/data/reports/M4/telemetry_gpu_stress_test_report_1mhz_M4.json) |
| **1MHz Weekend** | 1,000,000 Hz | **0.0096 ms** | 99.70% | [Report](file:///Users/tarekclarke/Resilient RAP/resilient-rap-framework/data/reports/M4/telemetry_gpu_stress_test_report_weekend_1mhz_3.6m_M4.json) |

> [!TIP]
> Each frequency run now includes a full set of supporting files (CSV results, GPU metrics, and timing reports) in the `data/reports/M4/` directory.

## 4. Next Steps
- Implement domain-specific clinical drift logic.
- Conduct a longitudinal stability test over a simulated race weekend at 1000Hz.
