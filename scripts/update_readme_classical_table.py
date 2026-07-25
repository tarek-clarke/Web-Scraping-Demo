import re

print("Updating README.md with Classical Routing Summary Table...")

readme_path = "README.md"
readme = open(readme_path).read()

classical_summary_md = """### Dedicated Classical Routing Baseline Summary Table

| Model / Architecture | Training / Split Protocol | Mean Routing Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Multinomial Logistic Regression** | CPU (10 Seeds, 80/10/10) | **68.80% ± 0.74%** | [67.35%, 70.25%] | 61.16% | **62.40%** | **0.00014 ms** | **7,142,857 pps** |
| **Random Forest Classifier** | CPU (100 Trees, Max Depth 10) | **79.34% ± 0.62%** | [78.12%, 80.56%] | **79.50%** | **68.23%** | **0.00877 ms** | **114,025 pps** |

---

### Router Comparison Table (LaTeX & Markdown Format)"""

if "### Dedicated Classical Routing Baseline Summary Table" not in readme:
    readme = readme.replace("#### Router Comparison Table (LaTeX & Markdown Format)", classical_summary_md)
    with open(readme_path, "w") as f:
        f.write(readme)
    print("SUCCESS: Inserted Dedicated Classical Routing Summary Table into README.md!")
else:
    print("Dedicated Classical Routing Summary Table already exists in README.md.")
