# Resilient RAP Framework

**Resilient API Adaptation Protocol** — End-to-end chaos engineering, adaptive routing, and stream reconciliation framework for heterogeneous telemetry data streams.

---

## Overview

The Resilient RAP framework evaluates adaptive stream reconciliation across **9 microservice domains**, **3 chaos/drift families**, **6 candidate reconcilers**, and **4 routing architectures** (classical CPU, GPU statevector simulation, and physical 156-qubit QPU).

### Core Components

- **Microservice Ingestion (9 Domains)**: OpenF1 Telemetry, Finnhub Financial Feeds, SpaceX Telemetry, OpenWeather Vectors, FDA Clinical Records, NHL Hockey Event Streams, OpenSky Aviation Vectors, UEFA Football Match Events, and SmartCity Transit Events (`smartcity_transit`).
- **Chaos Engineering (3 Drift Families)**:
  1. *JSON Structural*: Dropped/null keys and key modification.
  2. *LLM-Generated Schema Reformulation (Qwen)*: LLM semantic field renaming preserving lexical stems.
  3. *Syntactic Field Truncation/Drift*: Type alterations and field truncation.
- **Reconciliation Engine (6 Candidates)**: Levenshtein, Regex, BERT (MiniLM-v2), BGE Embedding, Cohere Embed (`embed-english-v3.0`), and Gemma 4 E2B (`gemma_e2b`).
- **Routing Architectures**:
  1. *Multinomial Logistic Regression (CPU)*: Linear decision boundary baseline.
  2. *Random Forest Classifier (CPU)*: Non-linear tree ensemble baseline (100 trees, max depth 10).
  3. *VQC Simulator Router (Aer GPU)*: 12-qubit Variational Quantum Classifier on AMD Instinct MI250X GPUs.
  4. *IBM QPU Router (Physical Hardware)*: 12-qubit VQC executed on 156-qubit IBM Heron r2 (`ibm_marrakesh`).
- **Aggregation Protocol**: Unweighted macro-average across 9 microservice APIs.
- **Instrumentation**: Power and execution profiling capabilities (`EnergyTracker`) for hardware monitoring.

---

## Hardware Execution Environments

| Platform / Target | Accelerator / Device Tier | Allocation | Execution Purpose |
| :--- | :--- | :---: | :--- |
| **LUMI-G (EuroHPC)** | AMD Instinct MI250X (ROCm) | 4 Cards / 8 GCDs (512GB VRAM) | BERT, BGE, Gemma & Qiskit Aer GPU Simulation |
| **IBM Quantum Platform** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | Physical QPU Execution Payload (`d9idh9d0k0jc738jf4ug`) |
| **Cohere Cloud API** | `embed-english-v3.0` | Cloud Dense Vector API | Remote Vector Representation Baseline |
| **Local Host** | 16-Core x86_64 CPU | System RAM | Classical Routers (Logistic Regression & Random Forest) |

---

## Active Benchmark Parameters (IBM Quantum)

The physical QPU benchmark execution results from IBM Quantum Platform:

* **Target QPU Backend**: `ibm_marrakesh` (IBM Heron r2, 156 Physical Qubits)
* **Job ID**: `d9idh9d0k0jc738jf4ug`
* **Held-out Workload**: 20,250 parameter sets (6,750 held-out cases × 3 repetitions)
* **Shots per Circuit**: 384 shots
* **Total QPU Executions**: 7,776,000 physical QPU executions
* **Total QPU execution time**: 2,308 s
* **Ansatz Config**: `ZZFeatureMap` (2 reps) + `RealAmplitudes` (2 reps) on 12 qubits
* **Execution Status**: **`COMPLETED`**

```json
{
  "backend": "ibm_marrakesh",
  "job_id": "d9idh9d0k0jc738jf4ug",
  "total_circuits": 20250,
  "shots_per_circuit": 384,
  "status": "complete",
  "quantum_seconds": 2308,
  "routing_accuracy": 0.4053
}
```

### Physical QPU Hardware Feasibility Analysis

A core empirical contribution of this work is evaluating the Variational Quantum Classifier (VQC) Quantum Router on physical quantum hardware (**IBM Heron r2**, `ibm_marrakesh`, 156 Physical Qubits) across **7,776,000 physical QPU executions** ($2,308 \text{ QPU seconds}$):

> **Hardware-Feasibility Finding**: Physical-QPU execution on IBM Heron r2 produced lower routing accuracy ($40.53\%$) than ideal GPU statevector simulation ($81.46\%$), consistent with hardware noise and execution effects.
>
> Fallback-protected reconciliation coverage is reported separately from first-choice routing accuracy.

---

## Reconciliation Baselines Performance (Across 9 APIs)

Evaluates end-to-end telemetry stream reconciliation accuracy and processing latency for individual candidate reconcilers across 9 microservice APIs:

| Reconciler Baseline | Acceleration / Hardware Target | GPU Allocation | Mean Reconciliation Acc. (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Levenshtein** | Local CPU | N/A | 75.00% | 0.343 ms | 2917.3 pps |
| **Regex** | Local CPU | N/A | 78.02% | 0.623 ms | 1606.3 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.76% | 36.751 ms | 27.2 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.76% | 4.594 ms | 217.7 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.68% | 38.532 ms | 26.0 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.68% | 4.816 ms | 207.6 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 74.34% | 453.348 ms | 2.2 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 46.69% | 3613.795 ms | 0.30 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 46.69% | 451.724 ms | 2.20 pps |

---

## Classical Routing Baselines & Leakage Controls

To evaluate the Variational Quantum Classifier (VQC) Quantum Router against conventional machine learning baselines, we implement two classical CPU-based routing models trained on the exact same 10-dimensional pre-reconciliation feature vectors ($x_0, \dots, x_9 \in [0, \pi]$) across **31,500 telemetry packets**:

1. **Multinomial Logistic Regression (CPU)**: A linear decision boundary baseline operating on normalized pre-reconciliation structural and edit-distance features.
2. **Random Forest Classifier (CPU)**: A non-linear ensemble baseline (100 decision trees, max depth 10) evaluating complex feature interactions.

### Dedicated Classical Routing Baseline Summary Table

| Model / Architecture | Training / Split Protocol | Mean Routing-Selection Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | Derived batch-amortized evaluation rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Multinomial Logistic Regression** | CPU (10 Seeds, 80/10/10) | **68.80% ± 0.74%** | [68.27%, 69.33%] | 61.16% | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Classifier** | CPU (100 Trees, Max Depth 10) | **79.34% ± 0.62%** | [78.90%, 79.78%] | **79.50%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |

---

### Router Comparison Table (LaTeX & Markdown Format)

```latex
\begin{table}[h]
\centering
\caption{Router Selection Baselines Comparison: Classical vs. VQC Quantum Router Models}
\label{tab:router_selection_comparison}
\begin{tabular}{lcccc}
\hline
\textbf{Router Selection Architecture} & \textbf{Hardware Target} & \textbf{Routing-Selection Acc. (\%)} & \textbf{LOAO Acc. (\%)} & \textbf{Inference Latency (ms)} \\
\hline
Theoretical Oracle Router (upper bound)  & Ideal Reference & 100.00\% & 100.00\% & 0.000 ms \\
Logistic Regression Router   & CPU (16 Cores)  & 68.80\% $\pm$ 0.74\% & 62.40\% & 0.00014 ms \\
Random Forest Router         & CPU (16 Cores)  & 79.34\% $\pm$ 0.62\% & 68.23\% & 0.00877 ms \\
VQC Simulator Router         & 4 MI250X Cards  & 81.46\% & N/A & 10.889 ms \\
IBM QPU Router (Heron r2)    & QPU (156 Qubits)& 40.53\% & N/A & 113.975 ms \\
\hline
\end{tabular}
\end{table}
```

| Router Selection Architecture | Hardware Target | Mean Routing-Selection Acc. (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms/packet) | Derived batch-amortized evaluation rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Theoretical Oracle Router (upper bound)** | Ideal Reference | **100.00%** | **100.00%** | **0.000 ms** | $\infty$ |
| **Logistic Regression Router** | CPU (16 Cores) | **68.80% ± 0.74%** | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Router** | CPU (16 Cores) | **79.34% ± 0.62%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | **81.46%** | N/A | **10.889 ms** | **91.8 pps** |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | **40.53%** | N/A | **113.975 ms** | **8.8 pps** |

---

## API-Specific Performance Tables

#### 1. OpenF1 Telemetry
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 83.52% | 0.228 ms | 4386.0 pps |
| **Regex** | Local CPU | N/A | 78.87% | 0.419 ms | 2386.6 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 93.79% | 75.437 ms | 13.3 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 93.79% | 9.430 ms | 106.0 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 93.50% | 9.718 ms | 102.9 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 93.50% | 1.215 ms | 823.2 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 83.94% | 437.518 ms | 2.3 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 42.10% | 3855.591 ms | 0.26 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 42.10% | 481.949 ms | 2.07 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 85.20% | 72.150 ms | 13.9 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 85.20% | 9.019 ms | 110.9 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **41.20%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 2. Finnhub Financial Feeds
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 71.50% | 0.062 ms | 16129.0 pps |
| **Regex** | Local CPU | N/A | 83.88% | 0.068 ms | 14705.9 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 83.22% | 76.295 ms | 13.1 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 83.22% | 9.537 ms | 104.9 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 81.75% | 10.120 ms | 98.8 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 81.75% | 1.265 ms | 790.5 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 71.62% | 534.078 ms | 1.9 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 60.97% | 3871.199 ms | 0.26 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 60.97% | 483.900 ms | 2.07 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 79.40% | 85.320 ms | 11.7 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 79.40% | 10.665 ms | 93.8 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **39.60%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 3. SpaceX Telemetry
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 67.01% | 0.083 ms | 12048.2 pps |
| **Regex** | Local CPU | N/A | 76.28% | 0.326 ms | 3067.5 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.69% | 2.332 ms | 428.8 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.69% | 0.291 ms | 3430.5 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 88.40% | 4.459 ms | 224.3 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 88.40% | 0.557 ms | 1794.1 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 74.68% | 374.031 ms | 2.7 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 40.09% | 2442.795 ms | 0.41 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 40.09% | 305.349 ms | 3.27 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 82.10% | 74.210 ms | 13.5 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 82.10% | 9.276 ms | 107.8 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **40.80%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 4. OpenWeather Vectors
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 68.80% | 0.019 ms | 52631.6 pps |
| **Regex** | Local CPU | N/A | 85.42% | 0.222 ms | 4504.5 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 86.69% | 11.304 ms | 88.5 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 86.69% | 1.413 ms | 707.7 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 85.36% | 19.025 ms | 52.6 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 85.36% | 2.378 ms | 420.5 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 70.87% | 391.680 ms | 2.6 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 50.50% | 3464.710 ms | 0.29 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 50.50% | 433.089 ms | 2.31 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 80.30% | 76.850 ms | 13.0 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 80.30% | 9.606 ms | 104.1 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **41.50%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 5. FDA Clinical Records
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 74.41% | 0.052 ms | 19230.8 pps |
| **Regex** | Local CPU | N/A | 73.01% | 0.163 ms | 6135.0 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 91.12% | 100.062 ms | 10.0 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 91.12% | 12.508 ms | 80.0 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 88.86% | 173.810 ms | 5.8 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 88.86% | 21.726 ms | 46.0 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 74.56% | 391.066 ms | 2.6 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 67.05% | 3735.446 ms | 0.27 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 67.05% | 466.931 ms | 2.14 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 83.90% | 112.450 ms | 8.9 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 83.90% | 14.056 ms | 71.1 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **38.90%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 6. NHL Hockey Event Streams
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 91.09% | 2.018 ms | 495.5 pps |
| **Regex** | Local CPU | N/A | 81.84% | 2.978 ms | 335.8 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 97.95% | 22.319 ms | 44.8 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 97.95% | 2.790 ms | 358.4 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 98.30% | 43.658 ms | 22.9 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 98.30% | 5.457 ms | 183.2 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 82.29% | 606.503 ms | 1.6 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 3.85% | 5524.083 ms | 0.18 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 3.85% | 690.510 ms | 1.45 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 89.10% | 94.600 ms | 10.6 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 89.10% | 11.825 ms | 84.6 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **42.10%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 7. OpenSky Aviation Vectors
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 48.92% | 0.012 ms | 83333.3 pps |
| **Regex** | Local CPU | N/A | 73.68% | 0.277 ms | 3610.1 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 65.28% | 22.816 ms | 43.8 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 65.28% | 2.852 ms | 350.6 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 61.09% | 53.552 ms | 18.7 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 61.09% | 6.694 ms | 149.4 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 43.63% | 350.798 ms | 2.9 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 71.92% | 1492.944 ms | 0.67 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 71.92% | 186.618 ms | 5.36 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 68.50% | 62.300 ms | 16.1 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 68.50% | 7.787 ms | 128.4 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **37.20%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 8. UEFA Football Match Events
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 84.18% | 0.299 ms | 3344.5 pps |
| **Regex** | Local CPU | N/A | 81.04% | 0.638 ms | 1567.4 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 94.99% | 7.754 ms | 129.0 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 94.99% | 0.969 ms | 1031.7 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 95.22% | 21.992 ms | 45.5 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 95.22% | 2.749 ms | 363.8 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 83.92% | 483.010 ms | 2.1 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 43.85% | 4125.083 ms | 0.24 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 43.85% | 515.635 ms | 1.94 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 84.60% | 81.100 ms | 12.3 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 84.60% | 10.137 ms | 98.6 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **42.80%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 9. SmartCity Transit Events
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 85.61% | 0.312 ms | 3205.1 pps |
| **Regex** | Local CPU | N/A | 68.20% | 0.512 ms | 1953.1 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 89.15% | 12.441 ms | 80.4 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 89.15% | 1.555 ms | 643.0 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 96.60% | 10.450 ms | 95.7 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 96.60% | 1.306 ms | 765.6 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 83.57% | 511.450 ms | 2.0 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 39.90% | 4012.300 ms | 0.25 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 39.90% | 501.538 ms | 1.99 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 80.04% | 125.000 ms | 8.0 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 80.04% | 15.625 ms | 64.0 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **40.70%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

---

## Reproducibility & Benchmark Methodology

To support reproducibility across all baseline models, classical classifiers, and quantum hardware executions:

1. **Aggregation Rule**: All global metrics represent an **unweighted macro-average across 9 microservice APIs**.
2. **Evaluation Protocol (10-Seed Sweep)**: Simulator and classical models are trained and evaluated across 10 random seeds ($N=10$) with 80/10/10 packet-identity splits.
3. **Data Leakage Controls**: Packets are grouped strictly by source record identity prior to splitting. Generalization is further evaluated via Leave-One-API-Out (LOAO) cross-validation where models train on 8 APIs and test exclusively on the 9th unseen API.
4. **Physical QPU Workload Protocol**: Physical QPU execution is performed under a single frozen QPU payload on **IBM Heron r2** (`ibm_marrakesh`, 156 physical qubits) comprising 20,250 circuits (6,750 held-out cases × 3 repetitions) executed at 384 shots per circuit (7,776,000 total QPU executions, Job ID `d9idh9d0k0jc738jf4ug`).
5. **Timing Metric Definitions**:
   - *Single-Packet Latency*: Measured wall-clock response time for processing a single packet.
   - *Batch-Normalized QPU Timing*: QPU execution walltime divided across total parameter sets ($113.975 \text{ ms/packet}$).
   - *Derived Batch-Amortized Evaluation Rate*: Computed via $\text{pps} = \frac{1000.0}{\text{Inference Latency (ms)}}$ for classical router evaluation, representing model decision throughput rather than end-to-end stream reconciliation pipeline throughput.

---

## Code & Artifact Reference

- **Master Benchmark Results JSON**: [`data/reports/master_benchmark_results.json`](data/reports/master_benchmark_results.json)
- **Classical Router Script**: [`scripts/run_classical_router_experiment.py`](scripts/run_classical_router_experiment.py)
- **Legacy Experiments Archive**: [`docs/LEGACY_EXPERIMENTS.md`](docs/LEGACY_EXPERIMENTS.md)
