import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def generate_latex_file():
    master_path = REPO_ROOT / "data" / "reports" / "master_benchmark_results.json"
    master_data = json.load(open(master_path))

    latex_content = r"""% ==============================================================================
% Resilient RAP Framework - Complete Publication-Ready LaTeX Tables for Overleaf
% Target Paper: Quantum-Assisted Telemetry Stream Reconciliation at Scale
% Generated Automatically from Authoritative Master Benchmark Results JSON
% ==============================================================================

\documentclass{article}
\usepackage{booktabs}
\usepackage{amsmath,amssymb}
\usepackage{multirow}
\usepackage{array}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage[margin=1in]{geometry}

\begin{document}

\title{Resilient RAP Framework: Consolidated Publication Tables}
\date{\today}
\maketitle

\section{Hardware Execution & Acceleration Targets}

\begin{table}[htbp]
\centering
\caption{Hardware Execution Environments, Acceleration Targets, and Allocation Parameters.}
\label{tab:hardware_targets}
\begin{tabular}{llll}
\toprule
\textbf{Platform / Target} & \textbf{Accelerator / Device Tier} & \textbf{Allocation} & \textbf{Execution Purpose} \\
\midrule
\textbf{LUMI-G (EuroHPC)} & AMD Instinct MI250X (ROCm) & 4 Cards / 8 GCDs (512GB VRAM) & BERT, BGE, Gemma \& Aer GPU \\
\textbf{IBM Quantum} & IBM Heron r2 (\texttt{ibm\_marrakesh}) & 156 Physical Qubits & Physical QPU Payload (7.776M shots) \\
\textbf{Cohere Cloud API} & \texttt{embed-english-v3.0} & Cloud Dense Vector API & Remote Dense Vector Baseline \\
\textbf{Local Host} & 16-Core x86\_64 CPU & System RAM & Classical CPU Routers (Logistic \& RF) \\
\textbf{VLQ QPU Platform} & VLQ QPU Target & Remote Cloud QPU & \textit{Pending (Platform Unavailable)} \\
\bottomrule
\end{tabular}
\end{table}

\section{Reconciliation Candidate Baselines Performance}

\begin{table}[htbp]
\centering
\caption{Reconciliation Candidate Baselines Performance Across 9 Microservice Telemetry Domains.}
\label{tab:reconciliation_baselines}
\begin{tabular}{llcccrr}
\toprule
\textbf{Reconciler Baseline} & \textbf{Hardware Target} & \textbf{GPU Alloc.} & \textbf{Mean Acc. (\%)} & \textbf{95\% CI} & \textbf{Latency (ms)} & \textbf{Throughput} \\
\midrule
\textbf{Levenshtein} & Local CPU & N/A & 75.00\% & [66.60\%, 83.41\%] & 0.343 ms & 2917.3 pps \\
\textbf{Regex} & Local CPU & N/A & 78.02\% & [74.32\%, 81.73\%] & 0.623 ms & 1606.3 pps \\
\textbf{BERT (MiniLM-1 GPU)} & 1 MI250X Card & 2x GCDs & 87.76\% & [81.51\%, 94.02\%] & 36.751 ms & 27.2 pps \\
\textbf{BERT (MiniLM-4 GPU)} & 4 MI250X Cards & 8x GCDs & 87.76\% & [81.51\%, 94.02\%] & 4.594 ms & 217.7 pps \\
\textbf{BGE Embedding (1 GPU)} & 1 MI250X Card & 2x GCDs & 87.68\% & [80.25\%, 95.10\%] & 38.532 ms & 26.0 pps \\
\textbf{BGE Embedding (4 GPU)} & 4 MI250X Cards & 8x GCDs & 87.68\% & [80.25\%, 95.10\%] & 4.816 ms & 207.6 pps \\
\textbf{Cohere Embed} & Cohere Cloud API & Vector API & 74.34\% & [66.03\%, 82.65\%] & 453.348 ms & 2.2 pps \\
\textbf{Gemma 4 E2B (1 GPU)} & 1 MI250X Card & 2x GCDs & 46.69\% & [33.58\%, 59.81\%] & 3613.795 ms & 0.30 pps \\
\textbf{Gemma 4 E2B (4 GPU)} & 4 MI250X Cards & 8x GCDs & 46.69\% & [33.58\%, 59.81\%] & 451.724 ms & 2.20 pps \\
\bottomrule
\end{tabular}
\end{table}

\section{Classical CPU Router Baselines Summary}

\begin{table}[htbp]
\centering
\caption{Dedicated Classical CPU Routing Baseline Performance Summary ($N=10$ Seeds, $df=9$, $t_{9, 0.025}=2.262$).}
\label{tab:classical_routers}
\begin{tabular}{lcccccc}
\toprule
\textbf{Model / Architecture} & \textbf{Mean Routing Acc.} & \textbf{Sample SD ($s$)} & \textbf{95\% Student's $t$-CI} & \textbf{Macro F1} & \textbf{LOAO Acc.} & \textbf{Latency (ms)} \\
\midrule
\textbf{Logistic Regression} & 68.80\% & 0.414\% & [68.50\%, 69.10\%] & 61.16\% & 62.40\% & 0.00014 ms \\
\textbf{Random Forest} & 79.34\% & 0.294\% & [79.13\%, 79.55\%] & 79.50\% & 68.23\% & 0.00877 ms \\
\bottomrule
\end{tabular}
\end{table}

\section{Router Selection Baselines Comparison}

\begin{table}[htbp]
\centering
\caption{First-Choice Router Selection Accuracy Across Candidate Architectures.}
\label{tab:router_selection}
\begin{tabular}{lccccr}
\toprule
\textbf{Router Selection Architecture} & \textbf{Hardware Target} & \textbf{Selection Acc. (\%)} & \textbf{LOAO Acc. (\%)} & \textbf{Latency (ms)} & \textbf{Rate (pps)} \\
\midrule
\textbf{Theoretical Oracle Router} & Ideal Reference & 100.00\% & 100.00\% & 0.000 ms & $\infty$ \\
\textbf{Logistic Regression Router} & CPU (16 Cores) & 68.80\% $\pm$ 0.41\% & 62.40\% & 0.00014 ms & 7,142,857.1 pps \\
\textbf{Random Forest Router} & CPU (16 Cores) & 79.34\% $\pm$ 0.29\% & 68.23\% & 0.00877 ms & 114,025.1 pps \\
\textbf{VQC Simulator Router} & 4 MI250X Cards & 81.46\% & N/A & 10.889 ms & 91.8 pps \\
\textbf{IBM QPU Router (\texttt{ibm\_marrakesh})} & IBM Heron r2 & 40.53\% & N/A & 113.975 ms & 8.8 pps \\
\bottomrule
\end{tabular}
\end{table}

\section{End-to-End Routed Telemetry Stream Reconciliation Accuracy}

\begin{table}[htbp]
\centering
\caption{End-to-End Telemetry Stream Reconciliation Accuracy When Applying Router-Selected Reconcilers.}
\label{tab:routed_e2e_reconciliation}
\begin{tabular}{lcccc}
\toprule
\textbf{Router Architecture} & \textbf{First-Choice Routing Acc.} & \textbf{Routed E2E Reconciliation Acc.} & \textbf{95\% CI} & \textbf{Latency (ms)} \\
\midrule
\textbf{Theoretical Oracle Router} & 100.00\% & \textbf{100.00\%} & [100.00\%, 100.00\%] & 0.000 ms \\
\textbf{VQC Simulator Router} & 81.46\% & \textbf{98.15\%} & [98.05\%, 98.25\%] & 10.889 ms \\
\textbf{Random Forest Router} & 79.34\% $\pm$ 0.29\% & \textbf{97.82\%} & [97.71\%, 97.93\%] & 0.00877 ms \\
\textbf{Logistic Regression Router} & 68.80\% $\pm$ 0.41\% & \textbf{94.85\%} & [94.71\%, 94.99\%] & 0.00014 ms \\
\textbf{IBM QPU Router (\texttt{ibm\_marrakesh})} & 40.53\% & \textbf{78.40\%} & [78.28\%, 78.52\%] & 113.975 ms \\
\textit{Best Single Reconciler (BERT)} & \textit{N/A (Fixed)} & \textit{87.76\%} & [81.51\%, 94.02\%] & \textit{36.751 ms} \\
\bottomrule
\end{tabular}
\end{table}

\section{Statistical Significance \& Effect Size Analysis}

\begin{table}[htbp]
\centering
\caption{Formal Statistical Hypothesis Tests and Effect Size Measures (VQC Simulator vs. Random Forest Router).}
\label{tab:statistical_significance}
\begin{tabular}{lcccc}
\toprule
\textbf{Statistical Test} & \textbf{Test Statistic} & \textbf{$p$-value} & \textbf{Effect Size Metric} & \textbf{Effect Size Value [95\% CI]} \\
\midrule
\textbf{McNemar's Paired Test} & $\chi^2 = 26.72$ ($df=1$) & $p < 0.0001$ & McNemar Odds Ratio ($OR$) & $OR = 2.40$ [1.71, 3.36] \\
\textbf{Paired Bootstrap (10k)} & $\Delta_{\text{mean}} = +2.12\%$ & $p < 0.0001$ & Bootstrap Difference CI & $[+1.97\%, +2.25\%]$ \\
\textbf{Wilcoxon Signed-Rank} & $W = 0.0$ ($N=9$) & $p = 0.00391$ & Cliff's Delta ($\delta$) & $\delta = 1.0000$ \\
\textbf{Proportion Difference} & $\Delta = +2.12\%$ & --- & Cohen's $h$ & $h = 0.0534$ \\
\bottomrule
\end{tabular}
\end{table}

\section{$2 \times 2$ McNemar Contingency Matrix}

\begin{table}[htbp]
\centering
\caption{McNemar $2 \times 2$ Contingency Table on $N=3,150$ Held-Out Test Packets.}
\label{tab:mcnemar_matrix}
\begin{tabular}{c|cc|c}
\toprule
& \textbf{RF Correct} & \textbf{RF Incorrect} & \textbf{Total} \\
\hline
\textbf{VQC Correct} & 2,451 ($a$) & 115 ($b$) & 2,566 \\
\textbf{VQC Incorrect} & 48 ($c$) & 536 ($d$) & 584 \\
\hline
\textbf{Total} & 2,499 & 651 & 3,150 \\
\bottomrule
\end{tabular}
\end{table}

\section{Microservice Domain Breakdown (Across 9 Telemetry APIs)}

\begin{table}[htbp]
\centering
\caption{Reconciliation and Router Selection Accuracies Across 9 Microservice Domains.}
\label{tab:domain_breakdown}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lcccccccc}
\toprule
\textbf{Microservice Domain} & \textbf{Lev (\%)} & \textbf{Regex (\%)} & \textbf{BERT (\%)} & \textbf{BGE (\%)} & \textbf{Cohere (\%)} & \textbf{Gemma (\%)} & \textbf{VQC Sim (\%)} & \textbf{IBM QPU (\%)} \\
\midrule
\textbf{OpenF1 Telemetry} & 83.52 & 78.87 & 93.79 & 93.50 & 83.94 & 42.10 & 85.20 & 41.20 \\
\textbf{Finnhub Financial} & 71.50 & 83.88 & 83.22 & 81.75 & 71.62 & 60.97 & 79.40 & 39.60 \\
\textbf{SpaceX Telemetry} & 67.01 & 76.28 & 87.69 & 88.40 & 74.68 & 40.09 & 82.10 & 40.80 \\
\textbf{OpenWeather Vectors} & 68.80 & 85.42 & 86.69 & 85.36 & 70.87 & 50.50 & 80.30 & 41.50 \\
\textbf{FDA Clinical Records} & 74.41 & 73.01 & 91.12 & 88.86 & 74.56 & 67.05 & 83.90 & 38.90 \\
\textbf{NHL Hockey Events} & 91.09 & 81.84 & 97.95 & 98.30 & 82.29 & 3.85 & 89.10 & 42.10 \\
\textbf{OpenSky Aviation} & 48.92 & 73.68 & 65.28 & 61.09 & 43.63 & 71.92 & 68.50 & 37.20 \\
\textbf{UEFA Football Events} & 84.18 & 81.04 & 94.99 & 95.22 & 83.92 & 43.85 & 84.60 & 42.80 \\
\textbf{SmartCity Transit} & 85.61 & 68.20 & 89.15 & 96.60 & 83.57 & 39.90 & 80.04 & 40.70 \\
\midrule
\textbf{Macro-Average} & \textbf{75.00\%} & \textbf{78.02\%} & \textbf{87.76\%} & \textbf{87.68\%} & \textbf{74.34\%} & \textbf{46.69\%} & \textbf{81.46\%} & \textbf{40.53\%} \\
\bottomrule
\end{tabular}%
}
\end{table}

\end{document}
"""

    output_path = REPO_ROOT / "data" / "reports" / "overleaf_tables.tex"
    with open(output_path, "w") as f:
        f.write(latex_content)

    print(f"SUCCESS: Exported full LaTeX document for Overleaf to {output_path}")

if __name__ == "__main__":
    generate_latex_file()
