import re

print("Updating README.md with exact Student's t-distribution 95% CIs and correct SDs...")

readme_path = "README.md"
content = open(readme_path).read()

# 1. Update Dedicated Classical Summary Table
old_classical_table = """| Model / Architecture | Training / Split Protocol | Mean Routing-Selection Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | Derived batch-amortized evaluation rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Multinomial Logistic Regression** | CPU (10 Seeds, 80/10/10) | **68.80% ± 0.74%** | [68.27%, 69.33%] | 61.16% | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Classifier** | CPU (100 Trees, Max Depth 10) | **79.34% ± 0.62%** | [78.90%, 79.78%] | **79.50%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |"""

new_classical_table = """| Model / Architecture | Training / Split Protocol | Mean Routing-Selection Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | Derived batch-amortized evaluation rate (pps) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Multinomial Logistic Regression** | CPU (10 Seeds, 80/10/10) | **68.80% ± 0.41%** | [68.50%, 69.10%] | 61.16% | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Classifier** | CPU (100 Trees, Max Depth 10) | **79.34% ± 0.29%** | [79.13%, 79.55%] | **79.50%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |"""

content = content.replace(old_classical_table, new_classical_table)

# 2. Update Router Selection Baselines Table (LaTeX & Markdown)
content = content.replace("68.80\\% $\\pm$ 0.74\\%", "68.80\\% $\\pm$ 0.41\\%")
content = content.replace("79.34\\% $\\pm$ 0.62\\%", "79.34\\% $\\pm$ 0.29\\%")
content = content.replace("**68.80% ± 0.74%**", "**68.80% ± 0.41%**")
content = content.replace("**79.34% ± 0.62%**", "**79.34% ± 0.29%**")

# 3. Update Appendix Section with exact Student's t-CI calculations
old_appendix = """### 1. Multinomial Logistic Regression (CPU)
* **Raw 10-Seed Routing Accuracies (%)**: `[68.12%, 69.45%, 68.30%, 69.05%, 68.75%, 69.20%, 68.50%, 69.10%, 68.80%, 68.73%]`
* **Sample Mean ($\mu$)**: $68.80\%$
* **Sample Std Dev ($s$)**: $0.74\%$
* **Standard Error ($SE = s / \sqrt{10}$)**: $0.234\%$
* **95% Confidence Interval**: $\mu \pm 1.96 \cdot SE = [68.27\%, 69.33\%]$

### 2. Random Forest Classifier (CPU)
* **Raw 10-Seed Routing Accuracies (%)**: `[79.15%, 79.80%, 78.95%, 79.40%, 79.25%, 79.70%, 78.90%, 79.55%, 79.35%, 79.35%]`
* **Sample Mean ($\mu$)**: $79.34\%$
* **Sample Std Dev ($s$)**: $0.62\%$
* **Standard Error ($SE = s / \sqrt{10}$)**: $0.196\%$
* **95% Confidence Interval**: $\mu \pm 1.96 \cdot SE = [78.90\%, 79.78\%]$"""

new_appendix = """### 1. Multinomial Logistic Regression (CPU)
* **Raw 10-Seed Routing Accuracies (%)**: `[68.12%, 69.45%, 68.30%, 69.05%, 68.75%, 69.20%, 68.50%, 69.10%, 68.80%, 68.73%]`
* **Sample Mean ($\mu$)**: $68.80\%$
* **Sample Std Dev ($s$)**: $0.414\%$
* **Standard Error ($SE = s / \sqrt{10}$)**: $0.1309\%$
* **Critical Value ($t_{9, 0.025}$)**: $2.262$ (Student's $t$-distribution, $df=9$)
* **95% Confidence Interval**: $\mu \pm t_{9, 0.025} \cdot SE = [68.50\%, 69.10\%]$

### 2. Random Forest Classifier (CPU)
* **Raw 10-Seed Routing Accuracies (%)**: `[79.15%, 79.80%, 78.95%, 79.40%, 79.25%, 79.70%, 78.90%, 79.55%, 79.35%, 79.35%]`
* **Sample Mean ($\mu$)**: $79.34\%$
* **Sample Std Dev ($s$)**: $0.294\%$
* **Standard Error ($SE = s / \sqrt{10}$)**: $0.0930\%$
* **Critical Value ($t_{9, 0.025}$)**: $2.262$ (Student's $t$-distribution, $df=9$)
* **95% Confidence Interval**: $\mu \pm t_{9, 0.025} \cdot SE = [79.13\%, 79.55\%]$"""

content = content.replace(old_appendix, new_appendix)

with open(readme_path, "w") as f:
    f.write(content)

print("SUCCESS: Updated README.md with exact Student's t-distribution 95% CIs and correct SDs!")
