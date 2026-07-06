# 🏁 AMD ACT II Hackathon — Dual Track Submission

This repository contains **two independent, containerized submissions** for the AMD ACT II Hackathon, both powered by a shared **Variational Quantum Classifier (VQC)** routing core.

---

## ⭐ Track 1: Q-Route Agent — Hybrid Token-Efficient Routing Agent

A quantum-accelerated model routing agent that decides in real-time whether to use a **local model (cost = $0 tokens)** or the **remote Fireworks AI API (cost = remote tokens)**. The VQC router extracts 10 features from each incoming query and runs an 11-qubit quantum circuit to classify query complexity — all at **zero token cost**.

**📂 Directory:** [`track1_agent/`](track1_agent/)

### Quick Start
```bash
cd track1_agent/
export FIREWORKS_API_KEY="your_key"

# Self-test (no API key needed)
python agent.py --test

# Batch mode
python agent.py --input tasks.json --output results.json

# Docker
docker-compose up --build
```

---

## 🦄 Track 3: ApexFlow AI — Unicorn Track

A self-healing, quantum-routed telemetry ingestion gateway for mission-critical IoT and autonomous edge systems. Features a live interactive dashboard with real-time F1 telemetry, chaos injection controls, side-by-side JSON diff visualization, and AMD Instinct GPU diagnostics.

**📂 Directory:** [`apexflow_dashboard/`](apexflow_dashboard/)

### Quick Start
```bash
cd apexflow_dashboard/
export FIREWORKS_API_KEY="your_key"

# Docker (requires AMD Instinct GPU with ROCm)
docker-compose up --build

# Port forward to local browser
ssh -L 5000:127.0.0.1:5000 user@your-amd-instance-ip
# Navigate to: http://localhost:5000
```

---

## 🧬 Shared Quantum Core

Both tracks share the same `src/routing/` module:

| Component | Description |
|-----------|-------------|
| `src/routing/quantum_router.py` | VQC circuit builder (ZZFeatureMap + RealAmplitudes) |
| `src/routing/feature_extractor.py` | Telemetry packet feature extraction (Track 3) |
| `src/routing/quantum_backends.py` | Abstract backend interface (Aer / IBM QPU) |
| `track1_agent/query_feature_extractor.py` | Text query feature extraction (Track 1) |

---

## 🏗️ Technology Stack

- **Quantum:** Qiskit + Qiskit Aer (VQC routing)
- **GPU:** AMD Instinct MI250X / MI300X (ROCm + PyTorch)
- **Cloud AI:** Fireworks AI API (Llama-3-70B)
- **Local Models:** Qwen/Qwen2.5-7B-Instruct, all-MiniLM-L6-v2
- **Web:** Flask + Chart.js + SSE
- **Containerization:** Docker + docker-compose
