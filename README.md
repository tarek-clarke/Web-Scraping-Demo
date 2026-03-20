# Cadillac F1 Telemetry Platform

[![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen)](.)
![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial-red.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)
![Docker](https://img.shields.io/badge/Docker-Enterprise--Hardened-blue)

**Hardware-Accelerated Real-Time Telemetry Processing for 2026 F1 Season**

**Compatibility:**
- Linux (Ubuntu 24.04 validated): AMD ROCm or NVIDIA CUDA
- macOS: Apple Silicon (M-Series)
- CPU Fallback: Standard x86 support across platforms

## Executive Summary

A production-ready telemetry spine that processes race-weekend scale loads with sub-millisecond p95 latency on enterprise GPUs and Apple Silicon, while preserving forensic traceability and local-first resilience.

**What this platform does well:**
- Sustains high-throughput telemetry processing under injected chaos
- Detects/reconciles corruption with GPU semantic + tensor pipelines
- Preserves continuity with local-first buffering and optional Kafka streaming
- Enforces tamper-evident provenance (SHA-256 hash chain)
- Tracks race-readiness via deterministic SLO gates

---

## 🏁 Publication Highlights (IEEE TKDE Submission)

### 1. The "Resilience Delta" (CPU vs. GPU)
Under high-stress "Budapest" conditions, standard CPU-only telemetry stacks consistently trip the circuit breaker and cease processing. This framework introduces a **GPU-Accelerated Semantic Safety Net** that repairs 100% of schema drift on-the-fly, maintaining 0% downtime across all high-end NVIDIA architectures (B200, H200, RTX 6000).

### 2. Semantic Reconciliation Ablation
Traditional character-distance methods (Levenshtein) fail when sensor namespaces drift semantically (e.g., `oil_temp` → `lubricant_thermal`). Our BERT-based reconciler achieves **85.7% accuracy** on these complex synonyms, where existing systems hit a 0% recovery floor.

---

## 📊 Cross-Platform Validation Results (3-Run Statistical Rigor)

The framework has been validated across eight runtime targets with **3 independent runs per profile**, measuring performance floor (`p50`), tail latency (`p95`), and resilience under 5% injected chaos.

| Runtime Target | Platform | Total Packets | Acceptance Rate (Mean) | p95 Latency (Mean) | Resilience Score (Mean) | Circuit Breaker (GPU) | Circuit Breaker (CPU) |
|---|---|---:|---:|---:|---:|---|---|
| NVIDIA B200 (Blackwell) | Linux + CUDA | 3,600,000 | 95.82% | 0.007 ms | **0.9994** | **0 Trips** ✅ | 2 Trips ❌ |
| NVIDIA H200 NVL (Hopper) | Linux + CUDA | 3,600,000 | 89.84% | **0.013 ms** | **0.9993** | **0 Trips** ✅ | 1 Trip ❌ |
| NVIDIA RTX PRO 6000 Ada | Linux + CUDA | 3,600,000 | 95.74% | 0.006 ms | **0.9995** | **0 Trips** ✅ | 1 Trip ❌ |
| NVIDIA RTX 5090 | Linux + CUDA | 3,600,000 | 95.76% | 0.010 ms | 0.9994 | 0 Trips ✅ | 1 Trip ❌ |
| NVIDIA GTX 1660 Ti | Linux + CUDA | 3,600,000 | 95.77% | 0.019 ms | 0.9995 | 0 Trips ✅ | 0 Trips ✅ |
| AMD Radeon RX 7900 XT | Linux + ROCm | 3,600,000 | 95.75% | 0.007 ms | 0.9994 | 0 Trips ✅ | 1 Trip ❌ |
| Apple M4 | macOS (MPS) | 3,600,000 | 95.75% | 0.003 ms | 0.9995 | 0 Trips ✅ | 0 Trips ✅ |
| Intel Core i5-12600K | x86 Fallback | 3,600,000 | 95.76% | N/A* | 0.9995 | N/A | 1 Trip ❌ |

> **Validation Evidence**: Results are archived in `data/reports/`. High-volume B200 runs (900k packets) demonstrate linear scaling without latency degradation.

---

## 🏗️ System Architecture & Data Flow

### Design Philosophy: Local-First Resilience
The architecture prioritizes trackside autonomy. Telemetry is validated and persisted to a high-speed SQLite WAL buffer *before* any remote synchronization occurs.

```mermaid
flowchart LR
    RF["Car RF Downlink<br/>(50 Hz telemetry)"]
    CB["Circuit Breaker<br/>Schema + cadence validators"]
    DLQ[("Dead Letter Queue<br/>SQLite")]
    EDGE[("Trackside Edge Buffer<br/>SQLite WAL + optional Kafka")]
    BERT["GPU Semantic<br/>Reconciliation<br/>BERT + cosine similarity"]
    AUDIT[("Audit Log<br/>SHA-256 hash chain")]
    SINK["War Room<br/>Global Sink"]

    RF --> CB
    CB -->|bad packets| DLQ
    CB -->|valid data| EDGE
    EDGE --> BERT
    BERT -->|reconciled| AUDIT
    AUDIT --> SINK
```

### GPU Kernel Capabilities
- **Semantic Reconciliation**: BERT-based encoding (all-MiniLM-L6-v2) for batched field mapping.
- **Anomaly Detection**: Vectorized z-score outlier detection (σ > 3.5) on hardware tensors.
- **Provenance Verification**: Batch hash-chain integrity checks via GPU-emulated SHA-256.

---

## 🚀 Quick Start

```bash
# 1. Setup Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Build Accelerated Ingest
python3 setup.py build_ext --inplace

# 3. Run Validation
PYTHONPATH="." python3 tools/telemetry_gpu_stress_test.py --packets 30000 --chaos 0.05
```

---

## 🚦 Run Profiles & Benchmarking

### Six-Benchmark Suite
The automated wrapper `tools/run_all_benchmarks.sh` executes the canonical 3-run suite:
1.  **Standard Standard (@ 5% chaos)**: High-load baseline.
2.  **Repair-Focus Realistic (@ 0.5% chaos)**: Tests DLQ recovery throughput.
3.  **Repair-Focus Ultra-Low (@ 0.1% chaos)**: Validates sub-microsecond latency floors.

### Diagnostic Mode
Enables fine-grained attribution of missed detections by chaos mode and sensor.
```bash
python3 tools/telemetry_gpu_stress_test.py --diagnostic --output-suffix _diag
```

---

## 🛠️ Operational Capabilities

| Capability | Module | Research Significance |
|---|---|---|
| **Semantic Repair** | `translator.py` | Eliminates DNFs caused by "unknown" sensor IDs. |
| **Tamper Evidence** | `audit_log.py` | Cryptographic proof of data linearity for forensic review. |
| **Jurisdiction Gate** | `geo_fence.py` | Enforces GDPR compliance at the edge during EU/Global races. |
| **SLO Tracking** | `slo.py` | Deterministic "Race-Ready" gating for automation. |

---

## 📈 Statistical Rigor & Aggregation

To reproduce the IEEE-grade results:
1.  Run the benchmark script multiple times (it will automatically generate `_Run2`, `_Run3`).
2.  Aggregate the statistical mean and standard deviation:
```bash
python3 tools/aggregate_benchmark_runs.py --dir data/reports/B200 --platform B200
```

---

## 🐳 Docker & Testing

- **Local Tests**: `PYTHONPATH="." pytest tests/ -v`
- **Docker Production**: `docker-compose -f docker-compose.production.yml up -d`
- **Engine Stress**: `python3 tools/stress_test_engine_temp.py`

---

## ⚖️ ADRs & Licensing

- **ADRs**: Key decisions on SQLite WAL, Circuit Breakers, and Hash Chains are in `docs/adr/`.
- **License**: PolyForm Noncommercial License 1.0.0.
- **Contact**: Tarek Clarke (tclarke91@proton.me)
