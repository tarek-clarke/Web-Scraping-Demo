import re

print("Adding Hosseini Resilience columns to README.md...")

readme_path = "README.md"
content = open(readme_path).read()

# 1. Update Reconciliation Baselines Table
old_rec_table = """| Reconciler Baseline | Acceleration / Hardware Target | GPU Allocation | Mean Reconciliation Acc. (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
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

new_rec_table = """| Reconciler Baseline | Acceleration / Hardware Target | GPU Allocation | Mean Reconciliation Acc. (%) | Hosseini Resilience ($R_{\\text{H}}$) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Levenshtein** | Local CPU | N/A | 75.00% | 0.7500 | 0.343 ms | 2917.3 pps |
| **Regex** | Local CPU | N/A | 78.02% | 0.7802 | 0.623 ms | 1606.3 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.76% | 0.8776 | 36.751 ms | 27.2 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.76% | 0.8776 | 4.594 ms | 217.7 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.68% | 0.8768 | 38.532 ms | 26.0 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.68% | 0.8768 | 4.816 ms | 207.6 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 74.34% | 0.7434 | 453.348 ms | 2.2 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 46.69% | 0.4669 | 3613.795 ms | 0.30 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 46.69% | 0.4669 | 451.724 ms | 2.20 pps |"""

content = content.replace(old_rec_table, new_rec_table)

# 2. Update Dedicated Classical Summary Table
old_classical_table = """| Model / Architecture | Training / Split Protocol | Mean Routing-Selection Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | Derived batch-amortized evaluation rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Multinomial Logistic Regression** | CPU (10 Seeds, 80/10/10) | **68.80% ± 0.74%** | [68.27%, 69.33%] | 61.16% | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Classifier** | CPU (100 Trees, Max Depth 10) | **79.34% ± 0.62%** | [78.90%, 79.78%] | **79.50%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |"""

new_classical_table = """| Model / Architecture | Training / Split Protocol | Mean Routing-Selection Acc. (%) | Hosseini Resilience ($R_{\\text{H}}$) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | Derived batch-amortized evaluation rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Multinomial Logistic Regression** | CPU (10 Seeds, 80/10/10) | **68.80% ± 0.74%** | **0.6880** | [68.27%, 69.33%] | 61.16% | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Classifier** | CPU (100 Trees, Max Depth 10) | **79.34% ± 0.62%** | **0.7934** | [78.90%, 79.78%] | **79.50%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |"""

content = content.replace(old_classical_table, new_classical_table)

# 3. Update Router Selection Baselines Table
old_router_table = """| Router Selection Architecture | Hardware Target | Mean Routing-Selection Acc. (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms/packet) | Derived batch-amortized evaluation rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Theoretical Oracle Router (upper bound)** | Ideal Reference | **100.00%** | **100.00%** | **0.000 ms** | $\\infty$ |
| **Logistic Regression Router** | CPU (16 Cores) | **68.80% ± 0.74%** | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Router** | CPU (16 Cores) | **79.34% ± 0.62%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | **81.46%** | N/A | **10.889 ms** | **91.8 pps** |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | **40.53%** | N/A | **113.975 ms** | **8.8 pps** |"""

new_router_table = """| Router Selection Architecture | Hardware Target | Mean Routing-Selection Acc. (%) | Hosseini Resilience ($R_{\\text{H}}$) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms/packet) | Derived batch-amortized evaluation rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Theoretical Oracle Router (upper bound)** | Ideal Reference | **100.00%** | **1.0000** | **100.00%** | **0.000 ms** | $\\infty$ |
| **Logistic Regression Router** | CPU (16 Cores) | **68.80% ± 0.74%** | **0.6880** | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Router** | CPU (16 Cores) | **79.34% ± 0.62%** | **0.7934** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | **81.46%** | **0.8146** | N/A | **10.889 ms** | **91.8 pps** |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | **40.53%** | **0.4053** | N/A | **113.975 ms** | **8.8 pps** |"""

content = content.replace(old_router_table, new_router_table)

# 4. Update End-to-End Routed Stream Reconciliation Table
old_e2e_table = """| Router Architecture | Hardware Target | First-Choice Routing Acc. (%) | Routed End-to-End Reconciliation Acc. (%) | Mean Inference Latency (ms) | Notes |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Theoretical Oracle Router (upper bound)** | Ideal Reference | 100.00% | **100.00%** | 0.000 ms | Theoretical upper bound reference |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | 81.46% | **98.15%** | 10.889 ms | Ideal 12-qubit GPU statevector simulation |
| **Random Forest Router (CPU)** | CPU (16 Cores) | 79.34% ± 0.62% | **97.82%** | 0.00877 ms | Non-linear tree ensemble baseline |
| **Logistic Regression Router (CPU)** | CPU (16 Cores) | 68.80% ± 0.74% | **94.85%** | 0.00014 ms | Linear decision boundary baseline |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | 40.53% | **78.40%** | 113.975 ms | Physical 156-qubit Heron r2 execution (gate noise sensitivity) |
| *Best Single Reconciler Baseline (BERT)* | *1 MI250X Card* | *N/A (Fixed)* | *87.76%* | *36.751 ms* | *Unrouted single reconciler baseline* |"""

new_e2e_table = """| Router Architecture | Hardware Target | First-Choice Routing Acc. (%) | Routed End-to-End Reconciliation Acc. (%) | Hosseini Resilience ($R_{\\text{H}}$) | Mean Inference Latency (ms) | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Theoretical Oracle Router (upper bound)** | Ideal Reference | 100.00% | **100.00%** | **1.0000** | 0.000 ms | Theoretical upper bound reference |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | 81.46% | **98.15%** | **0.9815** | 10.889 ms | Ideal 12-qubit GPU statevector simulation |
| **Random Forest Router (CPU)** | CPU (16 Cores) | 79.34% ± 0.62% | **97.82%** | **0.9782** | 0.00877 ms | Non-linear tree ensemble baseline |
| **Logistic Regression Router (CPU)** | CPU (16 Cores) | 68.80% ± 0.74% | **94.85%** | **0.9485** | 0.00014 ms | Linear decision boundary baseline |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | 40.53% | **78.40%** | **0.7840** | 113.975 ms | Physical 156-qubit Heron r2 execution (gate noise sensitivity) |
| *Best Single Reconciler Baseline (BERT)* | *1 MI250X Card* | *N/A (Fixed)* | *87.76%* | *0.8776* | *36.751 ms* | *Unrouted single reconciler baseline* |"""

content = content.replace(old_e2e_table, new_e2e_table)

with open(readme_path, "w") as f:
    f.write(content)

print("SUCCESS: Added Hosseini Resilience columns to README.md!")
