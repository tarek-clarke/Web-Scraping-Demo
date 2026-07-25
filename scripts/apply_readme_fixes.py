import re

print("Updating README.md with publication-critical fixes...")

readme_path = "README.md"
content = open(readme_path).read()

# 1. Wording fixes
content = content.replace("* **Total QPU Walltime**: 2,308 QPU seconds", "* **Total QPU execution time**: 2,308 s")
content = content.replace("To ensure 100% scientific reproducibility", "To support reproducibility")
content = content.replace("PUB payload", "QPU payload")
content = content.replace("[67.35%, 70.25%]", "[68.27%, 69.33%]")
content = content.replace("[78.12%, 80.56%]", "[78.90%, 79.78%]")

# 2. Separate Global Summary Table into Reconciliation Baselines vs Router Selection Baselines
old_global_sec = """## Global Performance Summary Across All 9 APIs

| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy | Measured Latency (ms/packet) | System Throughput (packets/sec) |
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
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 81.46% | 87.109 ms | 11.5 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 81.46% | 10.889 ms | 91.8 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **40.53%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |"""

new_global_sec = """## Reconciliation Baselines Performance (Across 9 APIs)

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
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 46.69% | 451.724 ms | 2.20 pps |"""

content = content.replace(old_global_sec, new_global_sec)

# 3. Update Classical Router Table & Router Comparison Table
old_classical_sec = """### Dedicated Classical Routing Baseline Summary Table

| Model / Architecture | Training / Split Protocol | Mean Routing Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Multinomial Logistic Regression** | CPU (10 Seeds, 80/10/10) | **68.80% ± 0.74%** | [67.35%, 70.25%] | 61.16% | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Classifier** | CPU (100 Trees, Max Depth 10) | **79.34% ± 0.62%** | [78.12%, 80.56%] | **79.50%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |

---

### Router Comparison Table (LaTeX & Markdown Format)

```latex
\\begin{table}[h]
\\centering
\\caption{Comprehensive Router Comparison: Classical vs. VQC Quantum Router Baselines}
\\label{tab:router_comparison}
\\begin{tabular}{lcccc}
\\hline
\\textbf{Router Architecture} & \\textbf{Hardware Target} & \\textbf{Routing Acc. (\\%)} & \\textbf{LOAO Acc. (\\%)} & \\textbf{Latency (ms/pkt)} \\\\
\\hline
Best Fixed Reconciler (BERT) & 1 MI250X Card & 87.76% & N/A & 36.751 ms \\\\
Oracle Router (Upper Bound)  & Ideal Reference & 100.00\\% & 100.00\\% & 0.000 ms \\\\
Logistic Regression Router   & CPU (16 Cores)  & 68.80\\% $\\pm$ 0.74\\% & 62.40\\% & 0.00014 ms \\\\
Random Forest Router         & CPU (16 Cores)  & 79.34\\% $\\pm$ 0.62\\% & 68.23\\% & 0.00877 ms \\\\
VQC Simulator Router         & 4 MI250X Cards  & 81.46% & 74.10\\% & 10.889 ms \\\\
IBM QPU Router (Heron r2)    & QPU (156 Qubits)& 40.53% & N/A & 113.975 ms \\\\
\\hline
\\end{tabular}
\\end{table}
```

| Router Architecture | Hardware Target | Mean Routing Acc. (%) | LOAO Cross-Val Acc. (%) | Mean Latency (ms/packet) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Best Fixed Reconciler (BERT)** | 1 MI250X Card | 87.76% | N/A | 36.751 ms | 27.2 pps |
| **Oracle Router (Upper Bound)** | Ideal Reference | **100.00%** | **100.00%** | **0.000 ms** | $\\infty$ |
| **Logistic Regression Router** | CPU (16 Cores) | **68.80% ± 0.74%** | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Router** | CPU (16 Cores) | **79.34% ± 0.62%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | **81.46%** | **74.10%** | **10.889 ms** | **91.8 pps** |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | **40.53%** | N/A | **113.975 ms** | **8.8 pps** |"""

new_classical_sec = """### Dedicated Classical Routing Baseline Summary Table

| Model / Architecture | Training / Split Protocol | Mean Routing-Selection Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | Batch-Amortized Model-Eval Rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Multinomial Logistic Regression** | CPU (10 Seeds, 80/10/10) | **68.80% ± 0.74%** | [68.27%, 69.33%] | 61.16% | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Classifier** | CPU (100 Trees, Max Depth 10) | **79.34% ± 0.62%** | [78.90%, 79.78%] | **79.50%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |

---

### Router Selection Baselines Comparison Table (LaTeX & Markdown Format)

Evaluates first-choice route selection accuracy across the 10 pre-reconciliation feature dimensions ($x_0, \\dots, x_9$). Note: End-to-end reconciliation accuracy for reconciler candidates (e.g. BERT 87.76%) is presented separately above.

```latex
\\begin{table}[h]
\\centering
\\caption{Router Selection Baselines Comparison: Classical vs. VQC Quantum Router Models}
\\label{tab:router_selection_comparison}
\\begin{tabular}{lcccc}
\\hline
\\textbf{Router Architecture} & \\textbf{Hardware Target} & \\textbf{Routing-Selection Acc. (\\%)} & \\textbf{LOAO Acc. (\\%)} & \\textbf{Inference Latency (ms)} \\\\
\\hline
Oracle Router (Upper Bound)  & Ideal Reference & 100.00\\% & 100.00\\% & 0.000 ms \\\\
Logistic Regression Router   & CPU (16 Cores)  & 68.80\\% $\\pm$ 0.74\\% & 62.40\\% & 0.00014 ms \\\\
Random Forest Router         & CPU (16 Cores)  & 79.34\\% $\\pm$ 0.62\\% & 68.23\\% & 0.00877 ms \\\\
VQC Simulator Router         & 4 MI250X Cards  & 81.46\\% & N/A & 10.889 ms \\\\
IBM QPU Router (Heron r2)    & QPU (156 Qubits)& 40.53\\% & N/A & 113.975 ms \\\\
\\hline
\\end{tabular}
\\end{table}
```

| Router Selection Architecture | Hardware Target | Mean Routing-Selection Acc. (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms/packet) | Batch-Amortized Model-Eval Rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Oracle Router (Upper Bound)** | Ideal Reference | **100.00%** | **100.00%** | **0.000 ms** | $\\infty$ |
| **Logistic Regression Router** | CPU (16 Cores) | **68.80% ± 0.74%** | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Router** | CPU (16 Cores) | **79.34% ± 0.62%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | **81.46%** | N/A | **10.889 ms** | **91.8 pps** |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | **40.53%** | N/A | **113.975 ms** | **8.8 pps** |"""

content = content.replace(old_classical_sec, new_classical_sec)

with open(readme_path, "w") as f:
    f.write(content)

print("SUCCESS: Updated README.md with all publication-critical fixes!")
