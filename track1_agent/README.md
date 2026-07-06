# ⭐ Q-Route Agent — Track 1: Hybrid Token-Efficient Routing Agent

A **quantum-accelerated (VQC) model routing agent** that autonomously decides whether to serve each incoming task using a **local model (cost = $0 tokens)** or the **remote Fireworks AI API (cost = remote tokens)**.

The goal: **pick the cheapest option every time, without falling below the accuracy threshold.**

---

## 🧠 Architecture

```
         ┌──────────────────────┐
         │   Incoming Query     │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  Feature Extraction  │  ← 10 features, cost = $0
         │  (char length, code  │
         │   markers, complexity│
         │   keywords, etc.)    │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  VQC Quantum Router  │  ← 11 qubits, cost = $0
         │  (ZZFeatureMap +     │
         │   RealAmplitudes)    │
         └───────┬──────┬───────┘
                 │      │
      Class 0    │      │   Class 1
      (Local)    ▼      ▼   (Remote)
         ┌───────────┐  ┌───────────┐
         │ Local LLM │  │ Fireworks │
         │ (FREE $0) │  │ AI API    │
         └─────┬─────┘  └───────────┘
               │
               ▼
         ┌───────────┐
         │ Local Eval│  ← Quality check, cost = $0
         │ (FREE $0) │
         └─────┬─────┘
               │
         Pass? ├── Yes → Return answer (total cost = $0)
               │
               └── No  → Escalate to Fireworks AI (cost = tokens)
```

---

## 🚀 Quick Start

### Self-Test (No API key needed)
```bash
python agent.py --test
```

### Interactive Mode
```bash
export FIREWORKS_API_KEY="your_key"
python agent.py
```

### Batch Mode (JSON input)
```bash
python agent.py --input tasks.json --output results.json
```

### Docker
```bash
export FIREWORKS_API_KEY="your_key"
docker-compose up --build
```

---

## ⚙️ Configuration

All settings are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCAL_MODEL_ID` | `Qwen/Qwen2.5-7B-Instruct` | HuggingFace model ID for local inference |
| `FIREWORKS_MODEL_ID` | `accounts/fireworks/models/llama-v3-70b-instruct` | Fireworks AI model endpoint |
| `FIREWORKS_API_KEY` | *(none)* | Fireworks AI API key |
| `CONFIDENCE_THRESHOLD` | `0.55` | Min VQC confidence to trust the "local" decision |
| `QUALITY_THRESHOLD` | `0.6` | Min local eval score before escalating to remote |

---

## 💰 Why This Wins

1. **Feature extraction = $0 tokens.** Pure local computation.
2. **VQC routing = $0 tokens.** Runs on Aer simulator in microseconds.
3. **Local model inference = $0 tokens.** All local tokens are free per Track 1 rules.
4. **Local eval = $0 tokens.** Quality validation is a free heuristic.
5. **Only complex queries go to Fireworks AI.** The VQC learns the decision boundary.

Most competitors will burn remote tokens on a routing LLM call before even processing the task. Our VQC router makes the routing decision for **exactly $0 tokens**.
