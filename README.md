# 🏎️ ApexFlow AI & Q-Route Agent
*Dual-Submission (Track 1 & Track 3) — AMD ACT II Hackathon*

This repository houses the unified codebase for Tarek Clarke's dual-track hackathon submission, bridging quantum-accelerated token routing and self-healing telemetry pipelines. 

---

## 🚀 Overview

### 🏎️ Track 1: Q-Route Agent (AI Agent Track)
An offline-first, token-efficient routing agent designed to complete natural language and reasoning tasks for **exactly $0$ remote tokens**.
*   **VQC Routing:** Utilizes an 11-qubit Variational Quantum Classifier (VQC) trained on a physical **156-qubit IBM Heron r2 QPU** (heavy hex lattice) to classify tasks locally.
*   **100% Offline Caching:** All model weights (Qwen-2.5-1.5B-Instruct) are pre-downloaded and baked directly into the Docker image layer, enabling immediate local execution with no runtime external API calls or internet dependencies.

### 🦄 Track 3: ApexFlow AI (Unicorn Track)
An autonomous, self-healing stream gateway designed to reconcile upstream database schema drifts and data value mutations in real-time.
*   **Self-Healing Pipeline:** Implements a three-tiered recovery loop (Local VQC -> ROCm-accelerated BERT -> Generative fallback) resolving schema drifts on streaming F1 telemetry.
*   **Interactive Dashboard:** A premium, dark-mode glassmorphic interface displaying live stream charts, JSON diff alignment, and dynamic hardware telemetry.
*   **AMD Validation:** Benchmark data compiled and validated on **AMD CDNA Instinct MI250X GPUs** on the LUMI-G supercomputer.

---

## 🛠️ Quick Start Instructions

### 🏎️ Track 1: Running the Agent (Docker)
The Track 1 agent is packaged into a self-contained, offline-ready `linux/amd64` container. To pull and execute it locally:

```bash
# 1. Pull the official image from Docker Hub
docker pull ventimochatrex/qroute-agent:latest

# 2. Run the agent against your test tasks (reads from tasks.json, outputs to results.json)
docker run --rm \
  -v $(pwd)/tasks.json:/input/tasks.json \
  -v $(pwd):/output \
  ventimochatrex/qroute-agent:latest
```

---

### 🦄 Track 3: Running the Dashboard (Local)
To start the interactive self-healing telemetry gateway dashboard on your local machine:

```bash
# 1. Install required dependencies
pip install flask transformers torch accelerate

# 2. Start the dashboard application
python3 apexflow_dashboard/app.py
```
👉 Open your browser and navigate to **`http://localhost:5001`** to interact with the live telemetry simulation.

---

## ⚙️ Core Technical Highlights

1.  **Quantum-Classical Hybrid Dispatcher:** 10 structural features of incoming packets are mapped in microseconds using an 11-qubit circuit with parameters trained directly on physical QPU hardware (IBM Heron r2).
2.  **AMD CDNA Hardware Validation:** Telemetry benchmarks and latency evaluations were executed natively on AMD Instinct GPUs under ROCm 6.1 on the LUMI-G HPC cluster.
3.  **Hosseini Resilience Index:** The gateway is mathematically validated to maximize data recovery ($C_{\text{rec}}$) under sustained 100% chaos injection rates.

---

## 🎓 Academic Context
This project represents a core practical validation component of Tarek Clarke's active PhD thesis research on resilient stream integration pipelines at **Tallinn University of Technology (TalTech)**.

---

## 📄 License
Open-sourced under the MIT License. Copyright (c) 2026 Tarek Clarke.