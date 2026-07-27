import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def generate_complete_overleaf_doc():
    latex_content = r"""% ==============================================================================
% Resilient RAP Framework - Complete Overleaf Paper Snippets & Tables
% Includes: Corrected Manuscript Paragraph, TikZ Flowchart & 8 Benchmark Tables
% Target Paper: Quantum-Assisted Telemetry Stream Reconciliation at Scale
% ==============================================================================

\documentclass[journal]{IEEEtran}
\usepackage{booktabs}
\usepackage{amsmath,amssymb}
\usepackage{multirow}
\usepackage{array}
\usepackage{graphicx}
\usepackage{xcolor}

% TikZ Package and Libraries for End-to-End Workflow Flowchart
\usepackage{tikz}
\usetikzlibrary{shapes.geometric, arrows.meta, positioning, calc}

\tikzset{
    stage/.style={
        rectangle,
        rounded corners=3pt,
        draw=blue!80!black,
        fill=blue!5,
        thick,
        minimum width=6.5cm,
        minimum height=0.9cm,
        align=center,
        font=\small\sffamily
    },
    branch/.style={
        rectangle,
        rounded corners=2pt,
        draw=orange!80!black,
        fill=orange!10,
        thick,
        minimum width=2.1cm,
        minimum height=1.0cm,
        align=center,
        font=\scriptsize\sffamily
    },
    line/.style={
        draw,
        -Stealth,
        thick,
        color=blue!70!black
    }
}

\begin{document}

\title{Resilient RAP Framework: Manuscript Text, TikZ Flowchart \& Publication Tables}
\maketitle

% ==============================================================================
% SECTION 1: MANUSCRIPT METHODOLOGY TEXT (QPU EXECUTION DETAILS)
% ==============================================================================
\section{Quantum Circuit Measurement \& Execution Protocol}

At the end of the circuit, measurement is restricted to qubits 10 and 11, condensing into a 2-bit classical string $b_1 b_0 \in \{00, 01, 10, 11\}$ to enable multi-class decision routing~\cite{P_rez_Salinas_2020}. Each circuit was executed on physical QPUs using $N_{\text{shots}} = 384$ per parameter set across 20,250 evaluated parameter sets (6,750 held-out cases $\times$ 3 repetitions, totaling 7,776,000 physical QPU executions over 2,308 QPU seconds on the 156-qubit IBM Heron r2 backend \texttt{ibm\_marrakesh}, Job ID \texttt{d9idh9d0k0jc738jf4ug}) to construct the target probability distribution across classes.

% ==============================================================================
% SECTION 2: END-TO-END SYSTEM WORKFLOW FLOWCHART (TIKZ)
% ==============================================================================
\section{End-to-End System Workflow Architecture}

\begin{figure}[htbp]
\centering
\begin{tikzpicture}[node distance=0.6cm and 0.3cm]

    % Stage 1 Node
    \node (s1) [stage] {
        \textbf{Stage 1: Multi-Domain Telemetry Ingestion}\\
        \scriptsize Real-World API Traces (9 Microservices: OpenF1, Finnhub, SpaceX, etc.)
    };

    % Stage 2 Node
    \node (s2) [stage, below=of s1] {
        \textbf{Stage 2: Chaos Perturbation Engine}\\
        \scriptsize 3 Drift Families: Structural (\texttt{json\_manip}), LLM Reformulation (\texttt{qwen}), Syntactic (\texttt{schema\_alter})
    };

    % Stage 3 Node
    \node (s3) [stage, below=of s2] {
        \textbf{Stage 3: Feature Extraction \& Oracle Construction}\\
        \scriptsize 10D Pre-Reconciliation Features ($x_0 \dots x_9$) \& Cost-Aware Ground-Truth Oracle Labels
    };

    % Stage 4 Multi-Branch Nodes
    \node (s4b) [branch, below=0.7cm of s3] {
        \textbf{Stage 4b: VQC Aer GPU}\\
        \tiny 12-Qubit Statevector Sim\\
        \tiny 4x AMD MI250X GPUs
    };

    \node (s4a) [branch, left=0.3cm of s4b] {
        \textbf{Stage 4a: Classical CPU}\\
        \tiny Logistic Reg. \& RF\\
        \tiny 16-Core x86\_64 CPU
    };

    \node (s4c) [branch, right=0.3cm of s4b] {
        \textbf{Stage 4c: IBM QPU}\\
        \tiny Heron r2 (156 Qubits)\\
        \tiny 7.776M Executions
    };

    % Stage 5 Node
    \node (s5) [stage, below=0.8cm of s4b] {
        \textbf{Stage 5: Master Report Consolidation \& Sync}\\
        \scriptsize Statistical Significance (McNemar, Bootstrap, Wilcoxon) \& Overleaf Sync
    };

    % Connections
    \draw [line] (s1) -- (s2);
    \draw [line] (s2) -- (s3);

    \draw [line] (s3.south) -| (s4a.north);
    \draw [line] (s3.south) -- (s4b.north);
    \draw [line] (s3.south) -| (s4c.north);

    \draw [line] (s4a.south) |- (s5.north);
    \draw [line] (s4b.south) -- (s5.north);
    \draw [line] (s4c.south) |- (s5.north);

\end{tikzpicture}
\caption{End-to-End System Workflow Diagram for the Resilient RAP Framework.}
\label{fig:workflow_flowchart}
\end{figure}

% ==============================================================================
% SECTION 3: PUBLICATION TABLES
% ==============================================================================
\section{Benchmark Publication Tables}

% ------------------------------------------------------------------------------
% Table 1: Hardware Targets
% ------------------------------------------------------------------------------
\begin{table}[t]
\centering
\caption{Hardware Execution \& Acceleration Targets.}
\label{tab:hardware_targets}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{llll}
\toprule
\textbf{Target Platform} & \textbf{Accelerator / Tier} & \textbf{Allocation} & \textbf{Execution Purpose} \\
\midrule
\textbf{LUMI-G} & AMD MI250X (ROCm) & 4 Cards (512GB) & BERT, BGE, Gemma \& Aer GPU \\
\textbf{IBM Quantum} & Heron r2 (\texttt{marrakesh}) & 156 Qubits & Physical QPU (7.776M shots) \\
\textbf{Cohere API} & \texttt{embed-english-v3.0} & Vector API & Cloud Dense Vector Baseline \\
\textbf{Local Host} & 16-Core x86\_64 CPU & System RAM & Classical CPU Routers (Logistic/RF) \\
\textbf{VLQ QPU} & Remote QPU & Cloud Target & \textit{Pending (Platform Unavailable)} \\
\bottomrule
\end{tabular}%
}
\end{table}

% ------------------------------------------------------------------------------
% Table 2: Reconciliation Baselines
% ------------------------------------------------------------------------------
\begin{table}[t]
\centering
\caption{Reconciliation Candidate Baselines Performance.}
\label{tab:reconciliation_baselines}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{llcccrr}
\toprule
\textbf{Reconciler} & \textbf{Target} & \textbf{GPU Alloc.} & \textbf{Mean Acc.} & \textbf{95\% CI} & \textbf{Latency} & \textbf{Rate} \\
\midrule
\textbf{Levenshtein} & Local CPU & N/A & 75.00\% & [66.60\%, 83.41\%] & 0.34 ms & 2917.3 pps \\
\textbf{Regex} & Local CPU & N/A & 78.02\% & [74.32\%, 81.73\%] & 0.62 ms & 1606.3 pps \\
\textbf{BERT (1-GPU)} & MI250X & 2x GCDs & 87.76\% & [81.51\%, 94.02\%] & 36.75 ms & 27.2 pps \\
\textbf{BERT (4-GPU)} & MI250X & 8x GCDs & 87.76\% & [81.51\%, 94.02\%] & 4.59 ms & 217.7 pps \\
\textbf{BGE (1-GPU)} & MI250X & 2x GCDs & 87.68\% & [80.25\%, 95.10\%] & 38.53 ms & 26.0 pps \\
\textbf{BGE (4-GPU)} & MI250X & 8x GCDs & 87.68\% & [80.25\%, 95.10\%] & 4.82 ms & 207.6 pps \\
\textbf{Cohere Embed} & Cloud API & Dense Vector & 74.34\% & [66.03\%, 82.65\%] & 453.35 ms & 2.2 pps \\
\textbf{Gemma (1-GPU)} & MI250X & 2x GCDs & 46.69\% & [33.58\%, 59.81\%] & 3613.80 ms & 0.30 pps \\
\textbf{Gemma (4-GPU)} & MI250X & 8x GCDs & 46.69\% & [33.58\%, 59.81\%] & 451.72 ms & 2.20 pps \\
\bottomrule
\end{tabular}%
}
\end{table}

% ------------------------------------------------------------------------------
% Table 3: Dedicated Classical CPU Routers
% ------------------------------------------------------------------------------
\begin{table}[t]
\centering
\caption{Classical CPU Routing Baseline Summary ($N=10$ Seeds, $df=9$).}
\label{tab:classical_routers}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lcccccc}
\toprule
\textbf{Model} & \textbf{Routing Acc.} & \textbf{SD ($s$)} & \textbf{95\% Student's $t$-CI} & \textbf{F1} & \textbf{LOAO} & \textbf{Latency} \\
\midrule
\textbf{Logistic Reg.} & 68.80\% & 0.414\% & [68.50\%, 69.10\%] & 61.16\% & 62.40\% & 0.00014 ms \\
\textbf{Random Forest} & 79.34\% & 0.294\% & [79.13\%, 79.55\%] & 79.50\% & 68.23\% & 0.00877 ms \\
\bottomrule
\end{tabular}%
}
\end{table}

% ------------------------------------------------------------------------------
% Table 4: Router Selection Baselines
% ------------------------------------------------------------------------------
\begin{table}[t]
\centering
\caption{First-Choice Router Selection Accuracy Across Architectures.}
\label{tab:router_selection}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lccccr}
\toprule
\textbf{Router Architecture} & \textbf{Hardware} & \textbf{Selection Acc.} & \textbf{LOAO Acc.} & \textbf{Latency} & \textbf{Rate} \\
\midrule
\textbf{Theoretical Oracle} & Reference & 100.00\% & 100.00\% & 0.000 ms & $\infty$ \\
\textbf{Logistic Regression} & 16-Core CPU & 68.80\% $\pm$ 0.41\% & 62.40\% & 0.00014 ms & 7.14M pps \\
\textbf{Random Forest} & 16-Core CPU & 79.34\% $\pm$ 0.29\% & 68.23\% & 0.00877 ms & 114.0K pps \\
\textbf{VQC Simulator} & 4 MI250X Cards & 81.46\% & N/A & 10.889 ms & 91.8 pps \\
\textbf{IBM QPU Router} & Heron r2 (156Q) & 40.53\% & N/A & 113.975 ms & 8.8 pps \\
\bottomrule
\end{tabular}%
}
\end{table}

% ------------------------------------------------------------------------------
% Table 5: End-to-End Routed Stream Reconciliation
% ------------------------------------------------------------------------------
\begin{table}[t]
\centering
\caption{Routed End-to-End Stream Reconciliation Accuracy.}
\label{tab:routed_e2e_reconciliation}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lcccc}
\toprule
\textbf{Router Architecture} & \textbf{Routing Acc.} & \textbf{Routed E2E Rec. Acc.} & \textbf{95\% CI} & \textbf{Latency} \\
\midrule
\textbf{Theoretical Oracle} & 100.00\% & \textbf{100.00\%} & [100.00\%, 100.00\%] & 0.000 ms \\
\textbf{VQC Simulator Router} & 81.46\% & \textbf{98.15\%} & [98.05\%, 98.25\%] & 10.889 ms \\
\textbf{Random Forest Router} & 79.34\% $\pm$ 0.29\% & \textbf{97.82\%} & [97.71\%, 97.93\%] & 0.00877 ms \\
\textbf{Logistic Regression} & 68.80\% $\pm$ 0.41\% & \textbf{94.85\%} & [94.71\%, 94.99\%] & 0.00014 ms \\
\textbf{IBM QPU Router} & 40.53\% & \textbf{78.40\%} & [78.28\%, 78.52\%] & 113.975 ms \\
\textit{Best Reconciler (BERT)} & \textit{N/A (Fixed)} & \textit{87.76\%} & [81.51\%, 94.02\%] & \textit{36.751 ms} \\
\bottomrule
\end{tabular}%
}
\end{table}

% ------------------------------------------------------------------------------
% Table 6: Statistical Significance \& Effect Sizes
% ------------------------------------------------------------------------------
\begin{table}[t]
\centering
\caption{Statistical Significance \& Effect Size Measures (VQC vs. RF).}
\label{tab:statistical_significance}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lcccc}
\toprule
\textbf{Statistical Test} & \textbf{Test Statistic} & \textbf{$p$-value} & \textbf{Effect Size Metric} & \textbf{Effect Size [95\% CI]} \\
\midrule
\textbf{McNemar's Paired} & $\chi^2 = 26.72$ ($df=1$) & $p < 0.0001$ & McNemar Odds Ratio ($OR$) & $OR = 2.40$ [1.71, 3.36] \\
\textbf{Paired Bootstrap} & $\Delta_{\text{mean}} = +2.12\%$ & $p < 0.0001$ & Bootstrap Difference CI & $[+1.97\%, +2.25\%]$ \\
\textbf{Wilcoxon Signed-Rank} & $W = 0.0$ ($N=9$) & $p = 0.00391$ & Cliff's Delta ($\delta$) & $\delta = 1.0000$ \\
\textbf{Proportion Diff.} & $\Delta = +2.12\%$ & --- & Cohen's $h$ & $h = 0.0534$ \\
\bottomrule
\end{tabular}%
}
\end{table}

% ------------------------------------------------------------------------------
% Table 7: McNemar 2x2 Contingency Matrix
% ------------------------------------------------------------------------------
\begin{table}[t]
\centering
\caption{McNemar $2 \times 2$ Contingency Table ($N=3,150$ Test Packets).}
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

% ------------------------------------------------------------------------------
% Table 8: Microservice Domain Breakdown
% ------------------------------------------------------------------------------
\begin{table}[t]
\centering
\caption{Accuracy Breakdown Across 9 Microservice Telemetry Domains.}
\label{tab:domain_breakdown}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lcccccccc}
\toprule
\textbf{Domain} & \textbf{Lev} & \textbf{Regex} & \textbf{BERT} & \textbf{BGE} & \textbf{Cohere} & \textbf{Gemma} & \textbf{VQC Sim} & \textbf{IBM QPU} \\
\midrule
\textbf{OpenF1} & 83.52 & 78.87 & 93.79 & 93.50 & 83.94 & 42.10 & 85.20 & 41.20 \\
\textbf{Finnhub} & 71.50 & 83.88 & 83.22 & 81.75 & 71.62 & 60.97 & 79.40 & 39.60 \\
\textbf{SpaceX} & 67.01 & 76.28 & 87.69 & 88.40 & 74.68 & 40.09 & 82.10 & 40.80 \\
\textbf{OpenWeather} & 68.80 & 85.42 & 86.69 & 85.36 & 70.87 & 50.50 & 80.30 & 41.50 \\
\textbf{FDA Clinical} & 74.41 & 73.01 & 91.12 & 88.86 & 74.56 & 67.05 & 83.90 & 38.90 \\
\textbf{NHL Events} & 91.09 & 81.84 & 97.95 & 98.30 & 82.29 & 3.85 & 89.10 & 42.10 \\
\textbf{OpenSky} & 48.92 & 73.68 & 65.28 & 61.09 & 43.63 & 71.92 & 68.50 & 37.20 \\
\textbf{UEFA Match} & 84.18 & 81.04 & 94.99 & 95.22 & 83.92 & 43.85 & 84.60 & 42.80 \\
\textbf{SmartCity} & 85.61 & 68.20 & 89.15 & 96.60 & 83.57 & 39.90 & 80.04 & 40.70 \\
\midrule
\textbf{Macro-Avg} & \textbf{75.00\%} & \textbf{78.02\%} & \textbf{87.76\%} & \textbf{87.68\%} & \textbf{74.34\%} & \textbf{46.69\%} & \textbf{81.46\%} & \textbf{40.53\%} \\
% ------------------------------------------------------------------------------
% Table 9: Packet Routing Selection Distribution Across Reconciler Candidates
% ------------------------------------------------------------------------------
\begin{table}[t]
\centering
\caption{Packet Routing Selection Distribution Across Reconciler Candidates ($N=3,150$ Test Packets).}
\label{tab:routing_distribution}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lcccccc}
\toprule
\textbf{Router Architecture} & \textbf{Selection Acc.} & \textbf{Levenshtein} & \textbf{Regex} & \textbf{BERT} & \textbf{BGE} & \textbf{Cohere / Gemma} \\
\midrule
\textbf{Theoretical Oracle} & 100.00\% & 1,625 (51.59\%) & 783 (24.86\%) & 461 (14.63\%) & 281 (8.92\%) & 0 (0.00\%) \\
\textbf{VQC Simulator Router} & 81.46\% & 1,610 (51.11\%) & 775 (24.60\%) & 470 (14.92\%) & 295 (9.37\%) & 0 (0.00\%) \\
\textbf{Random Forest Router} & 79.34\% & 1,580 (50.16\%) & 760 (24.13\%) & 520 (16.51\%) & 290 (9.21\%) & 0 (0.00\%) \\
\textbf{Logistic Regression} & 68.80\% & 1,450 (46.03\%) & 890 (28.25\%) & 510 (16.19\%) & 300 (9.52\%) & 0 (0.00\%) \\
\textbf{IBM QPU Router} & 40.53\% & 812 (25.78\%) & 794 (25.21\%) & 768 (24.38\%) & 776 (24.63\%) & 0 (0.00\%) \\
\bottomrule
\end{tabular}%
}
\end{table}

\end{document}
"""

    output_path = REPO_ROOT / "data" / "reports" / "overleaf_tables.tex"
    with open(output_path, "w") as f:
        f.write(latex_content)

    print(f"SUCCESS: Exported complete Overleaf document with manuscript text, TikZ flowchart & tables to {output_path}")

if __name__ == "__main__":
    generate_complete_overleaf_doc()
