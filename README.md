# Resilient Analytical Pipeline (RAP) Framework

![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen)
[![Licence](https://img.shields.io/badge/Licence-PolyForm%20Non--commercial-red.svg)](LICENSE)
[![CI](https://github.com/tarek-clarke/resilient-rap-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/tarek-clarke/resilient-rap-framework/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)
![Docker](https://img.shields.io/badge/Docker-Enterprise--Hardened-blue)

**Hardware-Accelerated Real-Time Telemetry Processing**

---

## Executive Summary

A production-ready telemetry spine that processes high-velocity data streams with sub-millisecond p95 latency on enterprise GPUs and Apple Silicon, while preserving forensic traceability and local-first resilience.

**Core Capabilities:**
- **Semantic Repair**: GPU-accelerated BERT kernels reconcile schema drift on-the-fly.
- **Microsecond Latency**: Sustains high-throughput on Blackwell, Hopper, and M4 architectures.
- **Forensic Provenance**: Tamper-evident SHA-256 hash chains for data integrity.
- **Edge Autonomy**: Local-first buffering with SQLite WAL and deterministic Gate SLOs.

---

## Why This Matters

In high-velocity environments like Formula 1 or Critical Care, **schema drift is a silent killer of data integrity.** Traditional pipelines react to drift by failing: dropping packets or triggering manual alerts that arrive too late. 

The Resilient RAP framework solves the **"Semantic Gap"**:
- **Zero-Loss Attribution**: Ensuring that a sensor renamed on-the-fly is still correctly attributed to its historical baseline.
- **Proactive Engineering**: Shifting from "Fixing the Pipeline" to "The Pipeline Fixes Itself."
- **Scientific Rigor**: Providing a proven, 3-tier safety net that maintains sub-millisecond p95 latency even under 1MHz saturation.

---

## Quick Start: Performance & Scaling Validation Suites

Follow these steps to replicate the sub-millisecond p95 latency benchmarks on your local hardware across all validation profiles.

### 1. Environment Setup
```bash
# Initialize virtual environment and dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Build accelerated C++ ingestion kernels for Tier 2 BERT inference
python3 setup.py build_ext --inplace
```

#### Generic HPC / Cluster Setup
For NVIDIA, AMD ROCm, or Apple Silicon systems, use the hardware-aware bootstrap:
```bash
source ./init_phd_env.sh
micromamba activate rap-env
python3 setup.py build_ext --inplace
```

If you just want to run the suite, the main entrypoint is one command:
```bash
./tools/run_smart_loop.sh
```

On Slurm clusters, submit the matching template instead:
```bash
sbatch configs/slurm/l40.conf
# or use the A100 preset as the closest datacenter template
```

### 2. Execute Validation Profiles

**Note:** The `--packets` argument denotes *packets per session* across 15 standard sessions. For example, `--packets 2000` translates to 30,000 total packets.

These explicit profile commands are optional examples; for most runs, the smart loop or Slurm template above is the recommended path.

#### Profile 1: Cross-Platform Baseline (100 Hz)
```bash
# Run Sprint Benchmark (30,000 total packets @ 5% chaos)
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.05 --output-suffix _sprint

# Run Race Weekend Benchmark (3.6M total packets @ 5% chaos)
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.05 --output-suffix _weekend
```

#### Profile 2: Concurrency & Team Scaling (Dual Car)
```bash
# Run Team Sprint (2 cars, 30k packets each, 60k total)
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.05 --team --output-suffix _team_sprint

# Run Team Weekend (2 cars, 3.6M packets each, 7.2M total)
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.05 --team --output-suffix _team_weekend
```

#### Profile 3: High-Frequency Stability Analysis (1kHz - 1MHz)
```bash
# Run 1kHz Sprint Validation
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --frequency 1000 --packets 2000 --chaos 0.05 --output-suffix _sprint_1000hz

# Run 1MHz Sprint Endurance Validation
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --frequency 1000000 --packets 2000 --chaos 0.05 --output-suffix _sprint_1mhz

# Run 1kHz Weekend Validation
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --frequency 1000 --packets 240000 --chaos 0.05 --output-suffix _weekend_1000hz

# Run 1MHz Sprint Endurance Validation
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --frequency 1000000 --packets 240000 --chaos 0.05 --output-suffix _weekend_1000hz
```

#### Profile 4: LLM Chaos Comparison
```bash
# Run Aggressive LLM Chaos baseline sprint
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 2000 --chaos-profile aggressive --chaos-strategy llm --llm-model gemma-4-e4b-it --output-suffix _llm_chaos_sprint
```

#### Automated Benchmark Suite (Smart Loop)
If you are running on a cloud instance (like an NVIDIA B300) or headless server, you can use the built-in smart loop to automatically execute **all** profiles 3 times, compute the p95 latency floors, and archive the outputs to `data/reports/`:
```bash
# Auto-detects hardware and loops the entire validation suite until 3 runs are complete
./tools/run_smart_loop.sh
```

### 3. Launch Real-Time Dashboard
To monitor the ingestion stream, circuit-breaker status, and autonomous repairs in real-time, launch the browser-based observability dashboard:
```bash
# Linux/macOS
PYTHONPATH="." python -m uvicorn src.api_server:app --host 0.0.0.0 --port 5050

# Windows PowerShell
$env:PYTHONPATH="."; python -m uvicorn src.api_server:app --host 0.0.0.0 --port 5050
```
Then open `http://localhost:5050/dashboard` in any browser.

---

## System Architecture: 3-Tier Resilient Reconciliation

The architecture prioritizes edge autonomy and "Self-Healing" resilience. Inbound telemetry is validated against a 3-tier reconciliation stack before forensic auditing.

```mermaid
flowchart TD
    RF["Ingress Downlink<br/>(100 Hz telemetry)"]
    CB["Circuit Breaker<br/>Schema + cadence validators"]
    
    subgraph RECON["3-Tier Reconciliation Stack"]
        direction TB
        CACHE["Tier 1: Verified Cache<br/>(O(1) Knowledge Base)"]
        BERT["Tier 2: Semantic Inference<br/>(O(n) GPU BERT)"]
        HITL["Tier 3: HITL Governor<br/>(Expert Correction)"]
        
        CACHE -- "Mismatch" --> BERT
        BERT -- "Low Confidence" --> HITL
        HITL -- "Human Validation" --> CACHE
    end
    
    DLQ[("Dead Letter Queue<br/>SQLite")]
    EDGE[("Edge Buffer<br/>SQLite WAL")]
    AUDIT[("Audit Log<br/>SHA-256 chain")]
    SINK["Central Sink"]
    
    RF --> CB
    CB -->|invalid| DLQ
    CB -->|valid| EDGE
    EDGE --> CACHE
    CACHE -- "Success" --> AUDIT
    BERT -- "Success" --> AUDIT
    AUDIT --> SINK
```

### Core Methodology: 3-Tier Active-Learning Loop

1.  **Tier 1: Verified Mapping Cache (O(1))**: Prioritizes previously human-validated mappings.
2.  **Tier 2: Semantic Inference (BERT)**: Utilizes GPU-accelerated BERT kernels to reconcile unseen drift.
3.  **Tier 3: Human-in-the-Loop Governor**: Fallback for low-confidence inferences.

---

## Research Highlights

### 1. The Resilience Delta (CPU vs. GPU)
Under high-stress conditions, standard CPU-only telemetry stacks consistently trip the circuit breaker and cease processing. This framework introduces a GPU-accelerated semantic safety net that repairs 100% of schema drift on-the-fly, maintaining zero downtime across all high-end NVIDIA architectures including Blackwell, Hopper, and Ada.

### 2. Reconciliation Ablation Study (BERT vs. Traditional)
A critical challenge in modern telemetry is **Sensor Name Drift** (e.g., from oil_temp to lubricant_thermal_deg). This framework justifies the use of BERT-based semantic reconciliation by comparing it against character-distance (Levenshtein) and rule-based (Regex) methods.

| Algorithm | Mean Accuracy | Avg Latency | Key Performance Gap |
| :--- | :--- | :--- | :--- |
| **BERT (all-MiniLM-L6-v2)** | **100.0%** | **~0.012 ms** | **Passes 100% of Synonym Drift** (e.g., *gas_reserve_pct*) |
| Levenshtein (Distance) | 28.6% | ~0.001 ms | Fails 100% of Synonyms; only detects typos. |
| Regex (Pattern Matching) | 85.7% | < 0.001 ms | Brilliant for known keywords; brittle for new sensor names. |

**Technical Conclusion:** While BERT introduces a slight latency overhead (+0.011 ms), it eliminates the 71.4% data loss floor seen in character-distance methods, ensuring zero-loss sensor attribution in evolving telemetry environments.

#### 3. Cross-Domain Portability (Healthcare)
To validate the framework's domain-agnostic capability, I applied the 3-tier architecture to **clinical telemetry** (FHIR-inspired vitals monitoring).

| Metric | Automotive (F1) | Healthcare (Clinical) |
| :--- | :--- | :--- |
| **Cold-Start Accuracy (BERT)** | 92.4% | 30.4% |
| **Forensic Confidence (Tier 3)** | 0.85+ | 0.65+ |
| **Healed Accuracy (Tier 1)** | 100.0% | 100.0% |

> [!TIP]
> **Clinical Insight**: The lower cold-start accuracy in clinical informatics underscores the necessity of the **Tier 3 Governor**, as medical acronyms (e.g., SpO2, RR) often require human forensic context that transformer models lack in zero-shot scenarios.

### 4. Cross-Domain Translation Table
The table below summarizes mappings observed from recent domain test runs. Use the dashboard to trigger new runs and expand this table automatically.

| Original Field | Translated Field | Domain | Confidence |
|---|---|---|---:|
| `post_engagement_metric` | `post_engagement` | social-media | 0.92 |
| `follower_cnt` | `user_follower_count` | social-media | 0.89 |
| `closing_price` | `closing_price` | finance | 1.00 |
| `daily_vol` | `daily_volume` | finance | 0.94 |
| `gas_reserve_pct` | `fuel_reserve_percentage` | automotive | 0.98 |
| `oil_temp` | `lubricant_temperature` | automotive | 0.97 |
| `pulse_bpm` | `heart_rate` | healthcare | 0.95 |
| `spo2_saturation` | `blood_oxygen_pct` | healthcare | 0.93 |
| `temp_c` | `temperature_celsius` | weather | 0.96 |
| `wind_speed_kph` | `wind_speed_kph` | weather | 0.94 |
| `alt_m` | `altitude_meters` | aerospace | 0.97 |
| `vel_mps` | `velocity_meters_per_second` | aerospace | 0.95 |
| `v_rms` | `voltage_rms` | smart-grid | 0.98 |
| `f_hz` | `frequency_hertz` | smart-grid | 0.96 |
| `goal_cnt` | `goals_scored` | hockey | 0.95 |
| `assist_cnt` | `assists` | hockey | 0.93 |
| `shots_on_target` | `shots_on_goal` | soccer | 0.96 |
| `possession_pct` | `possession_percentage` | soccer | 0.98 |
| `td_run` | `rushing_touchdowns` | football | 0.94 |
| `yd_gain` | `yards_gained` | football | 0.92 |
| `fg_pct` | `field_goal_percentage` | basketball | 0.97 |
| `reb_cnt` | `rebounds` | basketball | 0.95 |
| `hr_cnt` | `home_runs` | baseball | 0.96 |
| `era_val` | `earned_run_average` | baseball | 0.94 |
| `item_price_cents` | `price` | ecommerce | 0.90 |
| `qty_sold` | `units_sold` | ecommerce | 0.88 |

Notes:
- Table generated from JSON results in `docs/data/domain-tests/` (timestamped files).
- Confidence scores reflect Tier 2 BERT semantic inference probability.

---

## Performance & Scaling Validation

The framework has been validated across eight runtime targets with three independent runs per profile, measuring performance floor (p50), tail latency (p95), and resilience under 5% injected chaos.

### 1. Cross-Platform Baseline (100 Hz)

> [!NOTE]
> All hardware and concurrency benchmarks below represent the **Tier 2 (BERT Semantic Inference)** processing latency. This is the computational "Deep Inference" baseline and does not include the near-zero O(1) latency of Tier 1 (Verified Cache).

#### Profile: Sprint (30,000 packets)
| Runtime Target | Platform | Total Packets | p95 Latency (Mean) | Resilience Score | Status |
|---|---|---:|---:|---:|---|
| NVIDIA B200 (Blackwell) | Linux + CUDA | 30,000 | 0.008 ms | 0.9996 | [STABLE] |
| NVIDIA GH200 | Linux + CUDA | 30,000 | 0.022 ms | 0.9991 | [STABLE] |
| NVIDIA H200 NVL (Hopper) | Linux + CUDA | 30,000 | **0.006 ms** | 0.9995 | [STABLE] |
| NVIDIA RTX PRO 6000 Ada | Linux + CUDA | 30,000 | 0.007 ms | 0.9996 | [STABLE] |
| NVIDIA RTX 5090 | Linux + CUDA | 30,000 | 0.011 ms | 0.9996 | [STABLE] |
| NVIDIA GTX 1660 Ti | Linux + CUDA | 30,000 | 0.022 ms | 0.9995 | [STABLE] |
| AMD Radeon RX 7900 XT | Linux + ROCm | 30,000 | 0.008 ms | 0.9996 | [STABLE] |
| Apple M4 | macOS (MPS) | 30,000 | **0.004 ms** | **0.9997** | [STABLE] |
| Intel Core i5-12600K | x86 Fallback | 30,000 | N/A* | 0.9996 | [STABLE] |

#### Profile: Weekend (3,600,000 packets)
| Runtime Target | Platform | Total Packets | p95 Latency (Mean) | Resilience Score | Status |
|---|---|---:|---:|---:|---|
| NVIDIA B200 (Blackwell) | Linux + CUDA | 3,600,000 | 0.007 ms | **0.9994** | [RELIABLE] |
| NVIDIA GH200 | Linux + CUDA | 3,600,000 | 0.025 ms | 0.9991 | [RELIABLE] |
| NVIDIA H200 NVL (Hopper) | Linux + CUDA | 3,600,000 | **0.013 ms** | **0.9993** | [RELIABLE] |
| NVIDIA RTX PRO 6000 Ada | Linux + CUDA | 3,600,000 | 0.006 ms | **0.9995** | [RELIABLE] |
| NVIDIA RTX 5090 | Linux + CUDA | 3,600,000 | 0.010 ms | 0.9994 | [RELIABLE] |
| NVIDIA GTX 1660 Ti | Linux + CUDA | 3,600,000 | 0.019 ms | 0.9995 | [RELIABLE] |
| AMD Radeon RX 7900 XT | Linux + ROCm | 3,600,000 | 0.007 ms | 0.9994 | [RELIABLE] |
| Apple M4 | macOS (MPS) | 3,600,000 | **0.003 ms** | 0.9995 | [RELIABLE] |
| Intel Core i5-12600K | x86 Fallback | 3,600,000 | N/A* | 0.9995 | [RELIABLE] |

*\*N/A: x86 CPU Fallback does not support sub-microsecond hardware-timestamped p95 latency measurement in standard telemetry mode.*

### 2. Concurrency & Team Scaling
This profile validates the ability to handle two simultaneous telemetry streams on a single shared GPU.

#### Dual Car Benchmarking Comparison (NVIDIA GH200)
| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint** | Total Packets | 30,000 | 60,000 (30k/car) | 2x Load |
| **Sprint** | p95 Latency | < 0.023 ms | < 0.023 ms | No measurable overhead |
| **Weekend** | Total Packets | 3,600,000 | 7,200,000 | 2x Extreme Load |
| **Weekend** | p95 Latency | 0.025 ms | ~0.026 ms | +0.001 ms overhead |
| **Both** | Resilience Score | 0.9991 | 0.9991 | [STABLE] |

#### Dual Car Benchmarking Comparison (Apple M4)
| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint** | Total Packets | 30,000 | 60,000 (30k/car) | 2x Load |
| **Sprint** | p95 Latency | < 0.004 ms | < 0.006 ms | No measurable overhead |
| **Weekend** | Total Packets | 3,600,000 | 7,200,000 | 2x Extreme Load |
| **Weekend** | p95 Latency | 0.003 ms | 0.005 ms | No measurable overhead |
| **Both** | Resilience Score | 0.9995 | 0.9978 | [STABLE] |

#### Dual Car Benchmarking Comparison (AMD 7900XT)
| Profile | Metric | 1-Car (Normal) | 2-Car (Team) | Comparison |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint** | Total Packets | 30,000 | 60,000 (30k/car) | 2x Load |
| **Sprint** | p95 Latency | < 0.010 ms | < 0.010 ms | Negligible overhead |
| **Weekend** | Total Packets | 3,600,000 | 7,200,000 | 2x Extreme Load |
| **Weekend** | p95 Latency | 0.007 ms | ~0.008 ms | +0.001 ms overhead |
| **Both** | Resilience Score | 0.9994 | 0.9995 | [STABLE] |

### 3. High-Frequency Stability Analysis
The following matrices validate stability across synthetic frequencies (1kHz to 1MHz) for elite hardware architectures.

#### Stability Matrix: NVIDIA GH200
| Profile | Target Frequency | p95 Latency | Resilience Score | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint (30k total)** | 1,000 Hz (1kHz) | 0.022 ms | 0.9988 | [STABLE] |
| **Sprint (30k total)** | 1,000,000 Hz (1MHz) | 0.022 ms | 0.9988 | [STABLE] |
| **Weekend (3.6M total)** | 1,000 Hz (1kHz) | 0.024 ms | 0.9991 | [RELIABLE] |
| **Weekend (3.6M total)** | 1,000,000 Hz (1MHz) | 0.025 ms | 0.9991 | [RELIABLE] |

#### Stability Matrix: Apple M4
| Profile | Target Frequency | p95 Latency | Resilience Score | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint (30k total)** | 1,000 Hz (1kHz) | **0.009 ms** | 0.9967 | [STABLE] |
| **Sprint (30k total)** | 1,000,000 Hz (1MHz) | **0.009 ms** | 0.9970 | [STABLE] |
| **Weekend (3.6M total)** | 1,000 Hz (1kHz) | **0.004 ms** | 0.9971 | [RELIABLE] |
| **Weekend (3.6M total)** | 1,000,000 Hz (1MHz) | **0.005 ms** | 0.9969 | [RELIABLE] |

#### Stability Matrix: AMD Radeon RX 7900 XT
| Profile | Target Frequency | p95 Latency | Resilience Score | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint (30k total)** | 1,000 Hz (1kHz) | < 0.001 ms | 0.9989 | [STABLE] |
| **Sprint (30k total)** | 1,000,000 Hz (1MHz) | < 0.001 ms | 0.9990 | [STABLE] |
| **Weekend (3.6M total)** | 1,000 Hz (1kHz) | < 0.001 ms | 0.8820 | [RELIABLE] |
| **Weekend (3.6M total)** | 1,000,000 Hz (1MHz) | < 0.001 ms | 0.8699 | [RELIABLE] |

> [!TIP]
> **Performance Amortization**: p95 latency on the M4 actually improves during high-volume 'Weekend' runs (0.004ms) compared to short 'Sprint' runs (0.009ms), demonstrating the efficiency of the framework's GPU-accelerated batching kernels once warm.

### 4. LLM Chaos Comparison

I added an optional LLM-driven chaos mode that can use a local model through LM Studio or an Ollama-style endpoint. The current default model is `gemma-4-e4b-it`.

#### Comparison Summary

| Run | Packets | Acceptance | Rejected | Chaos | DLQ | p95 Latency | Corruption Detection | Resilience |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Standard baseline | 30,000 | 95.81% | 1,256 | 1,513 | 1,190 | 0.005 ms | 76.92% | 99.98% |
| Aggressive + Gemma mean | 30,000 | 92.38% | 2,285 | 3,590 | 2,219 | 0.021 ms | 63.65% | 99.98% |

#### What the smoke test showed

- I compared the archived 30k standard sprint run against the mean of three corrected 30k aggressive Gemma runs.
- The aggressive runs used `--chaos-profile aggressive` and `--chaos-strategy llm` with `gemma-4-e4b-it`.
- Aggressive chaos shifted strongly toward schema drift and string corruption: the mean schema-drift count rose from 251 to 1,300, and string-in-numeric rose from 190 to 867.
- The aggressive runs are now normalized under [data/solo/M4/aggressive/Run1](data/solo/M4/aggressive/Run1), [data/solo/M4/aggressive/Run2](data/solo/M4/aggressive/Run2), and [data/solo/M4/aggressive/Run3](data/solo/M4/aggressive/Run3).

#### Practical takeaway

- If LM Studio returns a valid JSON plan, the new path can bias chaos mode selection and mutation ranges/tokens.
- If the model is unavailable or the response is not usable, the framework safely falls back to the original random chaos behaviour.
- The aggressive profile is the right choice when you want the Gemma-backed run to stress the BERT reconciliation path harder than the standard baseline.

#### Aggressive mode

For heavier BERT stress, run the GPU suite with `--chaos-profile aggressive` alongside `--chaos-strategy llm`. That profile biases toward schema drift, adversarial string corruption, and wider numeric flips so the semantic reconciler has to work harder, and it stores runs under `data/solo/M4/aggressive/...` by default.

---

## Real-World Use Cases

### Formula 1 & Elite Motorsport
- **Dynamic Aero Testing**: Reconciling sensor aliasing during mid-session wing or floor swaps without losing calibration data.
- **Team Scaling**: Managing concurrent high-frequency streams (Driver 1 vs. Driver 2) on limited trackside hardware.

### Healthcare & ICU Monitoring
- **Legacy Integration**: Mapping heterogeneous bedside monitor outputs (e.g., SpO2 vs. Vitals_Heart) to a standardized clinical record.
- **Patient Safety**: Ensuring 100% data continuity during sensor dropouts or aliasing in high-acuity environments.

### Autonomous Systems
- **Sensor Fusion Drift**: Maintaining deterministic temporal sync when LiDAR/Radar schemas evolve across fleet-wide firmware updates.

---

## Real-Time Observability

The framework includes a browser-based observability dashboard for monitoring ingestion health, schema drift detection, and autonomous "Self-Healing" repairs.

![Observability Dashboard](assets/dashboard_demo.png)

### Dashboard Features
- **Circuit Breaker State**: Colour-coded status indicator (green: CLOSED, yellow: HALF_OPEN, red: OPEN).
- **DLQ Depth**: Live tracking of quarantined packets over time.
- **Edge Buffer**: Progress indicators for SQLite WAL utilisation and sync status.
- **SLO Monitoring**: Real-time evaluation of all 6 service level objectives.
- **Autonomous Repairs**: Live visualization of Tier 2 and Tier 3 reconciliation events.
- **Auto-Refresh**: Polls every 3 seconds for persistent real-time accuracy.

### Operational API Endpoints
A FastAPI-powered REST API exposes the pipeline's health, metrics, and operational controls.

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness and readiness probe status. |
| `/metrics` | GET | Live circuit breaker state and buffer utilisation. |
| `/slo` | GET | Real-time SLO evaluation against 6 production budgets. |
| `/reports` | GET | List and fetch specific benchmark report JSONs. |
| `/run` | POST | Trigger smoke or chaos tests through the pipeline. |
| `/run/chaos` | POST | Trigger a 20-packet chaos test (15% corruption). |
| `/circuit-breaker/reset` | POST | Manual circuit breaker reset to CLOSED. |
| `/dashboard` | GET | Serve the browser-based observability UI. |

Once the server is running (see Quick Start), access the **Interactive API Docs** at `http://localhost:5050/docs`.

---

## Limitations and Future Work

### Current Limitations
- **Latency Budget**: While p95 is excellent, the ~10µs BERT overhead at 1MHz makes single-threaded real-time ingestion tight; multi-threading is required for higher throughput.
- **Cold-Start Domains**: Zero-shot accuracy is lower in highly specialized domains (e.g., Clinical Informatics) without Tier 1 cache warm-up.

### Future Work
- **On-Device Quantization**: Implementing INT8/GGUF quantization for BERT to enable microsecond-level inference on low-power edge devices.
- **RL-Guided Repairs**: Using Reinforcement Learning to optimize Tier 3 HITL triggers and reduce expert-intervention frequency.
- **Multi-Modal Reconciliation**: Extending the RAP pipeline to reconcile visual (Video/FLIR) and textual (Log) telemetry streams.

---

## Development & CI

Quality gates triggered on every push:
- **Lint**: `flake8`
- **Coverage**: `pytest-cov` (**75% minimum**)
- **Stress Test**: Chaos engine (1,000 packets @ 15% corruption)
- **Forensic Audit**: Batch hash-chain integrity verification

---

## ADRs and Licencing

- **ADRs**: Key decisions are documented in `docs/adr/`.
- **Licence**: PolyForm Non-commercial Licence 1.0.0.
- **Contact**: Tarek Clarke (tclarke91@proton.me)
