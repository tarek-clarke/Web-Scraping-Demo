# 🏎️ ApexFlow AI — Unified Pitch Presentation & Video Script
*Dual-Submission (Track 1 + Track 3) — AMD ACT II Hackathon*

---

# PART 1: The Slide Deck (unified_presentation.md)

## Slide 1: Title Slide
### **ApexFlow AI**
*Quantum-Resilient Telemetry Ingestion & Intelligent Routing*

*   **Subtitle:** Autonomous, self-healing stream integration and token-efficient routing powered by AMD Instinct™ CDNA and Qiskit.
*   **Presenter:** Tarek Clarke (Doctoral Candidate, Tallinn University of Technology)
*   **Visual:** A dark background showing an entangled 11-qubit circuit model routing a dynamic telemetry data flow path.

---

## Slide 2: The Dual Challenges
### **Pipeline Downtime & Skyrocketing Token Costs**

*   **The Ingestion Problem (Track 3):** Upstream schema changes and value type shifts crash traditional parsers, causing catastrophic data blackouts in IoT, connected vehicle fleets, or aerospace streams.
*   **The Routing Dilemma (Track 1):** While Large Language Models (LLMs) can heal these drifts, calling cloud APIs on every packet is latency-heavy and consumes massive, cost-prohibitive token budgets.
*   **The Inefficiency:** Competitors run expensive LLMs just to parse and decide where to route, burning tokens before solving the task.

---

## Slide 3: The Unified Architecture
### **The Self-Healing Stream Dispatcher**

*   **1. Feature Extraction:** Normalizes drift metrics (character length, syntax density, code markers) into a 10-dimensional angle vector.
*   **2. VQC Edge Routing:** An 11-qubit Qiskit Variational Quantum Classifier (VQC) running locally on CPU/GPU simulators routes the packet in microseconds for **exactly $0$ remote tokens**.
*   **3. Multi-Tiered Healing:**
    *   *Simple drifts:* Fixed locally on AMD GPUs using character-distance and BERT models (**$0$ token cost**).
    *   *Complex drifts:* Escalated to generative models (Gemma-4-E4B-it / Qwen-2.5-7B) hosted locally via ROCm or remote cloud APIs.

---

## Slide 4: Real-time Demo & Dashboard
### **Self-Healing Telemetry in Action**

*   **Visualizing Schema Chaos:** Our live dashboard streams real-time Formula 1 telemetry under a sustained 100% schema drift load.
*   **Live VQC Routing:** Shows the VQC router classifying drifts on-the-fly, displaying confidence, latency, and routing paths.
*   **Bypass Caching:** Repeats of previously resolved drifts bypass neural inference entirely, executing in a near-instant $0.01\text{ ms}$.

---

## Slide 5: Hardware Acceleration & Economics
### **Optimized for AMD Instinct ROCm**

*   **GPU Integration:** Deploys local sentence-transformers (BERT) and LLMs directly on your AMD Instinct GPU allocation, dropping active GPU utilization from 100% to 15%.
*   **Platform Agnosticism:** The dashboard dynamically detects host platforms (displaying Apple Silicon locally and AMD Instinct MI300X/MI250X on Developer Cloud nodes).
*   **SaaS Viability:** Keeps cloud API token fees low, maintaining **$92\%+$ operating margins** for enterprise SLAs.

---

## Slide 6: Summary & Submission Links
### **Double-Submission Blueprint**

*   **Track 1 (AI Agent):** Pushed Docker container (**`ventimochatrex/qroute-agent:latest`**) ready for automated grading.
*   **Track 3 (Unicorn):** Complete open-source codebase, Docker files, and dashboard ready at:
    `https://github.com/tarek-clarke/resilient-rap-framework` (Branch: `amd-hackathon`)

---

# PART 2: The Video Presentation Script (180-Second Unified Pitch)

### **Visual Track**
*(0:00 - 0:20)* 
Show Slide 1. Webcam in the corner.

### **Audio / Speaking Track**
"Hello, I'm Tarek Clarke. I am a Doctoral Candidate at Tallinn University of Technology, and today I'm pitching ApexFlow AI—a unified, quantum-classical hybrid stream gateway that represents a core component of my PhD thesis on resilient data pipelines. This project addresses both Track 1 and Track 3 of the AMD ACT II Hackathon by combining intelligent routing and self-healing ingestion into a single, cohesive system."
"In mission-critical IoT, connected vehicle fleets, or aerospace streams, telemetry data is highly fragile. Upstream schema mutations and sensor upgrades cause traditional data pipelines to crash, leading to expensive downtime."

---

### **Visual Track**
*(0:20 - 0:50)*
Show Slide 2 and 3. Transition to showing your browser at `http://localhost:5001`.

### **Audio / Speaking Track**
"While Large Language Models can reconcile these schema drifts, running a heavy cloud LLM on every single telemetry packet destroys throughput and burns a massive, cost-prohibitive token budget."
"ApexFlow AI solves this by intercepting raw streams at the edge and utilizing a dual-pass hybrid pipeline. First, we extract 10 key structural features from the query or packet. These are encoded into rotation angles and evaluated in microseconds by an 11-qubit Variational Quantum Classifier (VQC) running locally on the node."
"The VQC makes the routing decision for exactly zero tokens, deciding whether to resolve the drift locally on our free edge resources, or escalate to a heavy generative model."

---

### **Visual Track**
*(0:50 - 1:25)*
**Action:** On the dashboard, select the driver "Lewis Hamilton", change the chaos method to "Nested Structs", and drag the slider to 100%. Highlight the red drifted JSON mapping to the green reconciled JSON.

### **Audio / Speaking Track**
"Let's look at the gateway in action, simulating real-time Formula 1 telemetry. As we inject severe structural schema chaos, the VQC router immediately classifies the drift. It maps simple key renames and value conversions to a local ROCm-accelerated BERT model—costing zero cloud tokens."
"If the local mapping fails a local quality evaluation check, the system escalates to generative models like Gemma or Qwen. However, once an anomaly is solved once, our bypass cache indexes it, executing subsequent repeat anomalies in a blistering 0.01 milliseconds."

---

### **Visual Track**
*(1:25 - 1:45)*
Point to the **AMD Instinct Telemetry** card on the dashboard showing the active temperature, power, and VRAM. Highlight the dynamic platform tag showing "Apple Silicon" or "AMD Instinct".

### **Audio / Speaking Track**
"Because this pipeline runs containerized with ROCm support, it harnesses the full power of AMD Instinct accelerators. The platform detection is completely dynamic, displaying our Apple Silicon development host locally, and switching to AMD Instinct hardware on Developer Cloud nodes."
"Our benchmarks show that utilizing the VQC edge-routing pipeline reduces active GPU utilization from 100% to just 15%, conserving node power and hardware resources."

---

### **Visual Track**
*(1:45 - 2:05)*
Show Slide 5 and 6 (Summary & Submission Links).

### **Audio / Speaking Track**
"For enterprise IoT systems, this tiered approach translates to 100% pipeline uptime and clean data feeds, with a 92% reduction in cloud token spend by keeping repetitive processing local."
"Our dual-track submission is fully complete: Track 1 is pushed as a headless, grading-compliant container at 'ventimochatrex/qroute-agent:latest', and Track 3 is hosted as a complete open-source prototype on GitHub. Thank you, and let's keep the data flowing."
