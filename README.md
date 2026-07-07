# 🏎️ ApexFlow AI & Q-Route Agent

*Dual-Submission (Track 1 & Track 3) — AMD Developer Hackathon: ACT II*

This repository houses the unified codebase for Tarek Clarke's dual-track hackathon submission, bridging quantum-accelerated token routing and self-healing telemetry pipelines.

---

## 🚀 Overview

### 🏎️ Track 1: Q-Route Agent (AI Agent Track)
An offline-first, token-efficient routing agent designed to complete natural language and reasoning tasks for **exactly $0$ remote tokens**.
*   **VQC Routing:** Utilizes an 11-qubit Variational Quantum Classifier (VQC) trained on a physical **156-qubit IBM Heron r2 QPU** (heavy hex lattice) to classify tasks locally.
*   **100% Offline Execution:** All model weights (`Qwen/Qwen2.5-1.5B-Instruct`) are pre-downloaded and baked directly into the Docker image layer, enabling immediate local inference with zero runtime network calls.

### 🦄 Track 3: ApexFlow AI (Unicorn Track)
An autonomous, self-healing stream gateway designed to reconcile upstream database schema drifts and data value mutations in real-time.
*   **Self-Healing Pipeline:** Implements a three-tiered recovery loop (Local VQC → ROCm-accelerated BERT → Generative fallback) resolving schema drifts on streaming F1 telemetry.
*   **Interactive Dashboard:** A premium, dark-mode glassmorphic interface displaying live stream charts, JSON diff alignment, and dynamic hardware telemetry.
*   **AMD Validation:** Benchmark data compiled and validated on **AMD CDNA Instinct MI250X GPUs** on the LUMI-G supercomputer.

> 📹 **[Demo Video →](https://youtu.be/TODO)**  *(Screen walkthrough of the live dashboard processing F1 telemetry streams)*

---

## 🛠️ Quick Start

### 🏎️ Track 1: Q-Route Agent (Docker)

The Track 1 agent is packaged into a self-contained, offline-ready `linux/amd64` container.

```bash
# 1. Pull the image
docker pull ventimochatrex/qroute-agent:latest

# 2. Copy the sample tasks file
cp tasks.example.json tasks.json

# 3. Run the agent
docker run --rm \
  -v $(pwd)/tasks.json:/input/tasks.json \
  -v $(pwd):/output \
  ventimochatrex/qroute-agent:latest

# 4. Inspect the output
cat results.json
```

A sample [`tasks.example.json`](tasks.example.json) is included in the repository root covering factual, code generation, summarization, sentiment, and math categories.

---

### 🦄 Track 3: ApexFlow Dashboard

#### Option A: Docker (Recommended)
The dashboard has its own Dockerfile at `apexflow_dashboard/Dockerfile`. To build and run:

```bash
# Build the Track 3 dashboard image
docker build -t apexflow-dashboard -f apexflow_dashboard/Dockerfile .

# Run the dashboard (exposed on port 5001)
docker run --rm -p 5001:5001 apexflow-dashboard
```

#### Option B: Local (pip)
```bash
# Install dependencies
pip install flask transformers torch accelerate

# Start the dashboard
python3 apexflow_dashboard/app.py
```

👉 Open your browser and navigate to **`http://localhost:5001`** to interact with the live telemetry simulation.

---

## ⚙️ Technical Highlights

| Component | Detail |
|---|---|
| **Quantum Router** | 11-qubit VQC with ZZFeatureMap + RealAmplitudes ansatz; parameters trained on IBM Heron r2 (156 physical qubits, heavy hex lattice) |
| **Local LLM** | `Qwen/Qwen2.5-1.5B-Instruct` — weights pre-cached inside Docker layer for 0-token offline inference |
| **Self-Healing Tiers** | Tier 1: Levenshtein/Regex (CPU) → Tier 2: BERT MiniLM-v2 (GPU) → Tier 3: Gemma-4-E4B-it generative fallback |
| **Hardware Validated** | AMD Instinct MI250X (CDNA2) on LUMI-G under ROCm 6.1 via SLURM |
| **Resilience Metric** | Hosseini Resilience Index applied to measure recovery capacity under sustained 100% chaos injection |

---

## 📂 Repository Structure

```
resilient-rap-framework/
├── track1_agent/              # Track 1: Q-Route offline agent
│   ├── agent.py               # Main agent entrypoint
│   ├── Dockerfile             # Self-contained linux/amd64 image
│   └── hf_cache/              # Pre-downloaded Qwen-1.5B weights
├── apexflow_dashboard/        # Track 3: Interactive dashboard
│   ├── app.py                 # Flask application
│   ├── Dockerfile             # ROCm-based dashboard image
│   └── static/                # CSS, JS, and assets
├── src/                       # Core pipeline modules
│   ├── chaos/                 # Chaos injection engines
│   ├── reconciliation/        # Levenshtein, Regex, BERT, Gemma reconcilers
│   ├── routing/               # Quantum VQC router + feature extractor
│   └── orchestration/         # Matrix executor
├── tasks.example.json         # Sample input for Track 1 testing
└── README.md
```

---

## 🎓 Academic Context

This project represents a core practical validation component of Tarek Clarke's active PhD thesis research on resilient stream integration pipelines at **Tallinn University of Technology (TalTech)**.

---

## 📄 License

Open-sourced under the MIT License. Copyright (c) 2026 Tarek Clarke.