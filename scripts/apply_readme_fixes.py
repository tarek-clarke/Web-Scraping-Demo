import re

print("Applying final publication edits to README.md...")

readme_path = "README.md"
content = open(readme_path).read()

# 1. Rename "System Throughput (packets/sec)" in Dedicated Classical Table to "Derived batch-amortized evaluation rate (pps)"
content = content.replace(
    "| Model / Architecture | Training / Split Protocol | Mean Routing Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | System Throughput (packets/sec) |",
    "| Model / Architecture | Training / Split Protocol | Mean Routing-Selection Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | Derived batch-amortized evaluation rate (pps) |"
)

# 2. Update Router Selection Baselines Comparison Table (LaTeX & Markdown)
# - Remove "Best Fixed Reconciler (BERT)" row from both LaTeX and Markdown
# - Change VQC Simulator LOAO from 74.10% to N/A in both LaTeX and Markdown
# - Rename throughput column header to "Derived batch-amortized evaluation rate (pps)"

old_latex_table = """```latex
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
```"""

new_latex_table = """```latex
\\begin{table}[h]
\\centering
\\caption{Router Selection Baselines Comparison: Classical vs. VQC Quantum Router Models}
\\label{tab:router_selection_comparison}
\\begin{tabular}{lcccc}
\\hline
\\textbf{Router Selection Architecture} & \\textbf{Hardware Target} & \\textbf{Routing-Selection Acc. (\\%)} & \\textbf{LOAO Acc. (\\%)} & \\textbf{Inference Latency (ms)} \\\\
\\hline
Oracle Router (Upper Bound)  & Ideal Reference & 100.00\\% & 100.00\\% & 0.000 ms \\\\
Logistic Regression Router   & CPU (16 Cores)  & 68.80\\% $\\pm$ 0.74\\% & 62.40\\% & 0.00014 ms \\\\
Random Forest Router         & CPU (16 Cores)  & 79.34\\% $\\pm$ 0.62\\% & 68.23\\% & 0.00877 ms \\\\
VQC Simulator Router         & 4 MI250X Cards  & 81.46\\% & N/A & 10.889 ms \\\\
IBM QPU Router (Heron r2)    & QPU (156 Qubits)& 40.53\\% & N/A & 113.975 ms \\\\
\\hline
\\end{tabular}
\\end{table}
```"""

content = content.replace(old_latex_table, new_latex_table)

old_md_table = """| Router Architecture | Hardware Target | Mean Routing Acc. (%) | LOAO Cross-Val Acc. (%) | Mean Latency (ms/packet) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Best Fixed Reconciler (BERT)** | 1 MI250X Card | 87.76% | N/A | 36.751 ms | 27.2 pps |
| **Oracle Router (Upper Bound)** | Ideal Reference | **100.00%** | **100.00%** | **0.000 ms** | $\\infty$ |
| **Logistic Regression Router** | CPU (16 Cores) | **68.80% ± 0.74%** | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Router** | CPU (16 Cores) | **79.34% ± 0.62%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | **81.46%** | **74.10%** | **10.889 ms** | **91.8 pps** |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | **40.53%** | N/A | **113.975 ms** | **8.8 pps** |"""

new_md_table = """| Router Selection Architecture | Hardware Target | Mean Routing-Selection Acc. (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms/packet) | Derived batch-amortized evaluation rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Oracle Router (Upper Bound)** | Ideal Reference | **100.00%** | **100.00%** | **0.000 ms** | $\\infty$ |
| **Logistic Regression Router** | CPU (16 Cores) | **68.80% ± 0.74%** | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Router** | CPU (16 Cores) | **79.34% ± 0.62%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | **81.46%** | N/A | **10.889 ms** | **91.8 pps** |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | **40.53%** | N/A | **113.975 ms** | **8.8 pps** |"""

content = content.replace(old_md_table, new_md_table)

# 3. Update Timing Metric Definitions in Reproducibility Section
content = content.replace(
    "- *System Throughput*: Computed via $\\text{pps} = \\frac{1000.0}{\\text{Measured Latency (ms)}}$.",
    "- *Derived Batch-Amortized Evaluation Rate*: Computed via $\\text{pps} = \\frac{1000.0}{\\text{Inference Latency (ms)}}$ for classical router evaluation, representing model decision throughput rather than end-to-end stream reconciliation pipeline throughput."
)

with open(readme_path, "w") as f:
    f.write(content)

print("SUCCESS: Applied final publication edits to README.md!")
