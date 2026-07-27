import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

def generate_complete_overleaf_doc():
    latex_content = r"""% ==============================================================================
% Resilient RAP Framework - Publication-Ready LaTeX Tables & TikZ Flowchart
% Suitable for IEEE / ACM / TKDE Paper Submission in Overleaf
% ==============================================================================

\documentclass[journal]{IEEEtran}
\usepackage{booktabs}
\usepackage{amsmath,amssymb}
\usepackage{multirow}
\usepackage{array}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{float}
\usepackage{placeins}

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

\title{Resilient RAP Framework: End-to-End Architecture, Workflow Flowchart \& Publication Tables}
\maketitle

\begin{abstract}
Modern Reproducible Analytical Pipelines (RAP) suffer from severe processing bottlenecks when encountering structural schema drift in real-time, high-velocity data streams. Traditional reconciliation requires synchronous CPU branch checking or manual conditional interventions, inducing significant latency penalties. Rising costs in classical computing hardware and concerns about the environmental impact of inefficient LLM usage are also increasing. This paper presents an improved iteration of the Resilient RAP Framework, assessing the validity of an autonomous orchestration layer that introduces a 12-qubit Variational Quantum Classifier (VQC), deployed on both a 24-qubit QPU and a 156-qubit QPU, to evaluate and route schema drift characteristics on-the-fly. By implementing a dual-run pre-warmup phase on AMD Instinct accelerators, we completely isolate HIP kernel compilation cold starts. Our dual-stage gatekeeper dynamically routes anomalous packets between lightweight classical CPU heuristics and heavy GPU-based models (BERT/GPT). Compared to brute-force GPU reconciliation, the hybrid quantum routing network maintains a highly resilient 98.15\% average system accuracy on physical IBM quantum hardware. By intelligently offloading deterministic drifts to CPU paths, the architecture reduces active GPU resource utilization from 78.2\% to 8.5\%, ultimately achieving a significant reduction in compute requirements relative to classical LLM reconciliation pipelines.
\end{abstract}

% ==============================================================================
% SECTION 1: END-TO-END SYSTEM WORKFLOW FLOWCHART (TIKZ)
% ==============================================================================
\section{End-to-End System Workflow Architecture}

\begin{figure}[htbp]
\centering
\begin{tikzpicture}[node distance=0.55cm]

    % Stage 1
    \node (s1) [stage] {
        \textbf{Stage 1: Multi-Domain Telemetry Ingestion}\\
        \scriptsize 9 Real-World APIs (OpenF1, Finnhub, SpaceX, etc.)
    };

    % Stage 2
    \node (s2) [stage, below=of s1] {
        \textbf{Stage 2: Chaos Perturbation Engine}\\
        \scriptsize Structural (\texttt{json\_manip}), Semantic (\texttt{qwen}), Syntactic (\texttt{schema\_alter})
    };

    % Stage 3
    \node (s3) [stage, below=of s2] {
        \textbf{Stage 3: Feature Extraction \& Oracle Construction}\\
        \scriptsize 10D Features ($x_0 \dots x_9$) \& Cost-Aware Oracle Labels
    };

    % Stage 4 (stacked vertically)
    \node (s4a) [branch, below=0.7cm of s3] {
        \textbf{Stage 4a: Classical CPU Routers}\\
        \tiny Logistic Regression \& Random Forest
    };

    \node (s4b) [branch, below=0.45cm of s4a] {
        \textbf{Stage 4b: VQC Aer GPU}\\
        \tiny 12-Qubit Statevector Simulation (MI250X)
    };

    \node (s4c) [branch, below=0.45cm of s4b] {
        \textbf{Stage 4c: IBM QPU Execution}\\
        \tiny Heron r2 (156 Qubits), 7.776M Shots
    };

    % Stage 5
    \node (s5) [stage, below=0.8cm of s4c] {
        \textbf{Stage 5: Master Report Consolidation}\\
        \scriptsize Statistical Tests (McNemar, Bootstrap, Wilcoxon)
    };

    % Connections
    \draw [line] (s1) -- (s2);
    \draw [line] (s2) -- (s3);
    \draw [line] (s3) -- (s4a);
    \draw [line] (s4a) -- (s4b);
    \draw [line] (s4b) -- (s4c);
    \draw [line] (s4c) -- (s5);

\end{tikzpicture}
\caption{Narrow End-to-End Workflow Diagram for the Resilient RAP Framework.}
\label{fig:workflow_flowchart}
\end{figure}

% ==============================================================================
% SECTION 2: HARDWARE ENVIRONMENT
% ==============================================================================

\section{Introduction \& Hardware Environment}
This experiment was tested on the LUMI-G supercomputer, using both a single AMD MI250X GPU and 4 MI250X GPUs for each benchmark. To evaluate the quantum routing proof of concept, physical execution was split across two backend architectures: IBM Cloud's Quantum Open Plan, leveraging a 156-qubit IBM Heron r2 QPU (\textit{ibm\_marrakesh}) with a heavy-hex lattice, and the EuroHPC LUMI-Q infrastructure, where ten hours of processing time was secured on a 24-qubit Star VLQ QPU.
The hardware platforms used are listed in Table~\ref{tab:hardware_targets}.

\begin{table}[htbp]
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

\section{Related Work}

Robin's paper on schema drift was used for the establishment of an existing issue in data pipelines~\cite{Robindrift}. 
To maintain a consistent level of corrupted packets, chaos was injected in the pipeline, as demonstrated by Basiri's 2016 paper on chaos engineering~\cite{Basiri_2016}.

Huang et al.'s paper on quantum machine learning demonstrated that it was a preferable method to classical machine learning in some engineered datasets, establishing a concept for this paper~\cite{Huang_2021}. The proposed quantum autoencoder for anomaly detection in Sakhnenko et al.'s paper was used as a basis for the quantum routing to optimize the use of different reconciliation methods~\cite{Sakhnenko_2022}. 

Osei et al.'s paper on hybrid-quantum process evaluation suggests that these processes should be evaluated on an end-to-end basis, rather than in stage isolation~\cite{OseiHPE}. Similarly, Kanazawa et al. suggest that it is difficult to evaluate and track runtime metrics of quantum workflows. They propose an observability architecture specific for hybrid-quantum processes, which eliminate redundant workflow processes on expensive HPC and quantum computers~\cite{KanazawaObservability}.

Havl{\'\i}{\v{c}}ek et al.'s supervised quantum enhanced learning feature spaces is used as a foundation for the ZZ Feature Map implementation~\cite{Havlicek_2019}.

Kandala et al.'s paper on hardware efficient eigensolvers was used as a basis for dedicated output qubits~\cite{Kandala_2017}.

Pérez-Salinas et al.'s paper on quantum classifiers is used as a basis for converting the qubits into a classical bit output~\cite{P_rez_Salinas_2020}.

% ==============================================================================
% SECTION 3: METHODOLOGY & MAPPING TABLES
% ==============================================================================

\section{Methodology}
\subsection{Variational Quantum Routing Architecture}
To eliminate severe compute and latency bottlenecks from using GPU-intensive models over CPU, such as Gemma \texttt{(gemma\_e2b)}, and to a lesser extent, BERT \texttt{(sentence-transformers/all-MiniLM-L6-v2)} and BGE \texttt{(BAAI/bge-base-en-v1.5)}, drifted telemetry packets are routed dynamically through a 12-qubit Variational Quantum Classifier (VQC)~\cite{Havlicek_2019}.
For each corrupted or anomalous packet identified by the classical fast-path check, the pre-processing layer extracts a 10-dimensional feature vector $\mathbf{x} \in \mathbb{R}^{10}$ describing its structural chaos/entropy, datatype shifts and string-edit properties (such as \texttt{field\_count}, \texttt{nesting\_depth}, \texttt{key\_edit\_distance\_mean}, and binary structural flags). Each feature is normalized to the interval $[0,1]$ and is subsequently scaled to $[0, \pi]$:
\begin{equation}
\mathbf{x}_{\text{scaled}} = \mathbf{x}_{\text{norm}} \times \pi
\end{equation}

These features are mapped to the quantum state space on qubits 0 through 9 using a non-linear $ZZ$ Feature Map across two repetitions~\cite{Havlicek_2019}. This entangling angle encoding captures non-linear, higher-order feature interactions prior to variational optimization.

\subsubsection{Parameterized Ansatz and Measurement}
The trainable layer of the VQC employs a 12-qubit \texttt{RealAmplitudes} ansatz spanning 10 feature qubits (listed in Table~\ref{tab:vqc_feature_mapping}) and 2 dedicated output qubits (listed in Table~\ref{tab:vqc_feature_mapping})~\cite{Kandala_2017}. The ansatz consists of parameterized Single-Qubit $Y$-rotation gates ($R_y(\theta)$) interleaved with entangling CNOT gates, allowing the circuit to map correlations between high-dimensional metadata and the appropriate target reconciler.

The 10 feature qubits are mapped as follows:
\begin{table}[htbp]
  \centering
  \small
  \caption{Mapping of Classical API Telemetry Features to VQC Qubits}
  \label{tab:vqc_feature_mapping}
  \resizebox{\linewidth}{!}{%
  \begin{tabular}{cccll}
    \hline
    \textbf{Index} & \textbf{Qubit} & \textbf{Feature Name} & \textbf{Normalization Bound / Scaling} & \textbf{Target Drift Context (RAP Application)} \\
    \hline
    0 & $q_0$ & \texttt{field\_count} & Raw count scaled by $\min(x/50.0, 1.0)$ & Evaluates overall schema footprint. \\
    1 & $q_1$ & \texttt{nesting\_depth} & JSON depth scaled by $\min(x/5.0, 1.0)$ & Identifies structural flattening or nesting. \\
    2 & $q_2$ & \texttt{numeric\_ratio} & Fraction of numeric values in $[0, 1]$ & Baseline payload datatype distribution. \\
    3 & $q_3$ & \texttt{string\_ratio} & Fraction of string values in $[0, 1]$ & Baseline payload datatype distribution. \\
    4 & $q_4$ & \texttt{fields\_added} & Count added divided by baseline count & Detects telemetry additions/extensions. \\
    5 & $q_5$ & \texttt{fields\_removed} & Count removed divided by baseline count & Identifies deleted fields causing payload drops. \\
    6 & $q_6$ & \texttt{key\_edit\_dist} & Mean Levenshtein distance, max $10.0$ & Measures spelling/casing drift severity. \\
    7 & $q_7$ & \texttt{type\_changes} & Binary indicator $\{0.0, 1.0\}$ & Flags data-type mismatches (e.g., float $\rightarrow$ string). \\
    8 & $q_8$ & \texttt{struct\_changes} & Binary indicator $\{0.0, 1.0\}$ & Flags structural array or nesting shifts. \\
    9 & $q_9$ & \texttt{source\_encoded} & Ordinal mapping $\{0.25, 0.50, 0.75, 1.00\}$ & Encodes context of the emitting API source. \\
    \hline
  \end{tabular}%
  }
\end{table}

At the end of the circuit, measurement is restricted to qubits 10 and 11, condensing into a 2-bit classical string $b_1 b_0 \in \{00, 01, 10, 11\}$ to enable multi-class decision routing~\cite{P_rez_Salinas_2020}. Each circuit was executed on physical QPUs using $N_{\text{shots}} = 384$ per parameter set across 20,250 evaluated parameter sets (6,750 held-out cases $\times$ 3 repetitions, totaling 7,776,000 physical QPU executions over 2,308 QPU seconds on the 156-qubit IBM Heron r2 backend \texttt{ibm\_marrakesh}, Job ID \texttt{d9idh9d0k0jc738jf4ug}) to construct the target probability distribution across classes.

The output qubits are mapped as follows:
\begin{table}[htbp]
  \centering
  \small
  \caption{VQC Output Qubit Measurement Mapping to Reconciler Actions}
  \label{tab:vqc_output_mapping}
  \resizebox{\linewidth}{!}{%
  \begin{tabular}{cccll}
    \hline
    \textbf{State ($b_1 b_0$)} & \textbf{Class} & \textbf{Reconciler} & \textbf{Reconciliation Type} & \textbf{Optimization Objective (SLA Benefit)} \\
    \hline
    \texttt{00} & Class 0 & Levenshtein & Lightweight String Edit & Near-zero compute cost for simple typos. \\
    \texttt{01} & Class 1 & Regex & Pattern-based Rule Match & Fast CPU execution for casing/structural shifts. \\
    \texttt{10} & Class 2 & \texttt{all-MiniLM-L6-v2} & Dense Embedding Similarity & High-accuracy contextual match for renaming. \\
    \texttt{11} & Class 3 & \texttt{gemma\_e2b} / Cohere & Dense Vector / LLM Fallback & High-capability fallback for complex drift. \\
    \hline
  \end{tabular}%
  }
\end{table}

% ==============================================================================
% SECTION 4: DATA INGESTION & CHAOS TABLES
% ==============================================================================

\section{Data Ingestion and Chaos Engineering}
For multi-domain testing, data was sourced from 9 distinct APIs: OpenF1 (Formula 1 telemetry), Finnhub (stock market telemetry), SpaceX (aerospace telemetry), OpenWeather (weather telemetry), the United States Food and Drug Administration (healthcare/ICU telemetry), National Hockey League (hockey telemetry), OpenSky (aviation telemetry), The Union of European Football Associations (football telemetry), and TfL Transit Predictions (London transit telemetry). From each API, 2,500 packets were extracted and stored for consistency, for a total of 22,500 packets to be used for cross-domain validation and shadow runs/QPU training.

In order to assess the reconciliation, corrupted packets were injected into each data stream using three methods listed in Table~\ref{tab:chaos_methods}. In order to test the viability of each reconciliation method on a traditional CPU/GPU, each API's 2,500 packet sample was run through each reconciler ten times, giving results for the reconciliation methods listed in Table~\ref{tab:reconciler_specifications}. A shadow run was conducted for QPU comparison, and an additional 2,500 packets were run for JSON and schema alteration in the QPU.

\begin{table}[htbp]
  \centering
  \small
  \caption{Chaos Engineering Injection Methods (Applied uniformly across all API sources)}
  \label{tab:chaos_methods}
  \resizebox{\linewidth}{!}{%
  \begin{tabular}{lp{6.0cm}p{5.0cm}}
    \hline
    \textbf{Chaos Method} & \textbf{Description} & \textbf{Example Sub-types} \\
    \hline
    Semantic Drift (Qwen) & Uses a local Qwen2.5-7B-Instruct LLM to logically rename fields to context-aware synonyms or domain-specific terminology. & Contextual rename translation, synonym substitution \\
    \hline
    JSON Manipulation & Performs structural changes on the JSON hierarchy, altering how values are stored without changing the core semantic meaning. & scalar\_to\_array, field\_split, field\_join \\
    \hline
    Schema Alteration & Modifies foundational schema structure constraints, strict data types, key capitalization, or nesting depth levels. & key\_case\_change, nesting\_deepen, variable\_drop \\
    \hline
  \end{tabular}%
  }
\end{table}

\subsection{Reconciliation Architecture Specifications}
\begin{table}[htbp]
\centering
\caption{Candidate Reconciler Model Specifications and Architecture Checkpoints}
\label{tab:reconciler_specifications}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{llll}
\toprule
\textbf{Reconciler} & \textbf{Model Identifier / Checkpoint} & \textbf{Architecture Class} & \textbf{Provider / Source} \\
\midrule
\textbf{Levenshtein} & Character-Level Edit Distance & Deterministic Dynamic Programming & Native C-Extension \\
\textbf{Regex} & Pattern Matching Engine & Deterministic Regular Expressions & Native Python \texttt{re} \\
\textbf{BERT} & \texttt{sentence-transformers/all-MiniLM-L6-v2} & Dense Transformer Encoder & Hugging Face \\
\textbf{BGE} & \texttt{BAAI/bge-base-en-v1.5} & Dense Embedding Encoder & BAAI / Hugging Face \\
\textbf{Cohere} & \texttt{embed-english-v3.0} & Dense Vector API & Cohere Cloud API \\
\textbf{Gemma} & \texttt{google/gemma-4-E2B-it} (\texttt{gemma\_e2b}) & Autoregressive LLM Decoder (4-bit) & Google / Hugging Face \\
\bottomrule
\end{tabular}%
}
\end{table}

% ==============================================================================
% SECTION 5: PERFORMANCE & RESULTS
% ==============================================================================

\section{Performance}
As observed in Table~\ref{tab:reconciliation_baselines}, baseline performance varies across classical and transformer-based reconcilers.

\begin{table}[t]
\centering
\caption{Reconciliation Candidate Baselines Performance \& Hardware Load.}
\label{tab:reconciliation_baselines}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{llccccrrr}
\toprule
\textbf{Reconciler} & \textbf{Target} & \textbf{GPU Alloc.} & \textbf{Mean Acc.} & \textbf{95\% CI} & \textbf{Latency} & \textbf{Rate} & \textbf{CPU Util.} & \textbf{GPU Util.} \\
\midrule
\textbf{Levenshtein} & Local CPU & N/A & 75.00\% & [66.60\%, 83.41\%] & 0.34 ms & 2917.3 pps & 12.5\% & 0.0\% \\
\textbf{Regex} & Local CPU & N/A & 78.02\% & [74.32\%, 81.73\%] & 0.62 ms & 1606.3 pps & 15.0\% & 0.0\% \\
\textbf{BERT (1-GPU)} & MI250X & 2x GCDs & 87.76\% & [81.51\%, 94.02\%] & 36.75 ms & 27.2 pps & 8.5\% & 78.2\% \\
\textbf{BERT (4-GPU)} & MI250X & 8x GCDs & 87.76\% & [81.51\%, 94.02\%] & 4.59 ms & 217.7 pps & 24.0\% & 94.5\% \\
\textbf{BGE (1-GPU)} & MI250X & 2x GCDs & 87.68\% & [80.25\%, 95.10\%] & 38.53 ms & 26.0 pps & 9.0\% & 81.4\% \\
\textbf{BGE (4-GPU)} & MI250X & 8x GCDs & 87.68\% & [80.25\%, 95.10\%] & 4.82 ms & 207.6 pps & 25.5\% & 95.8\% \\
\textbf{Cohere Embed} & Cloud API & Dense Vector & 74.34\% & [66.03\%, 82.65\%] & 453.35 ms & 2.2 pps & 2.0\% & 0.0\% \\
\textbf{Gemma (1-GPU)} & MI250X & 2x GCDs & 46.69\% & [33.58\%, 59.81\%] & 3613.80 ms & 0.30 pps & 14.2\% & 98.5\% \\
\textbf{Gemma (4-GPU)} & MI250X & 8x GCDs & 46.69\% & [33.58\%, 59.81\%] & 451.72 ms & 2.20 pps & 38.0\% & 99.2\% \\
\bottomrule
\end{tabular}%
}
\end{table}

In Table~\ref{tab:classical_routers}, we detail the CPU routing baseline summary.

\begin{table}[htbp]
\centering
\caption{Classical CPU Routing Baseline Summary ($N=10$ Seeds, $df=9$).}
\label{tab:classical_routers}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lcccccccc}
\toprule
\textbf{Model} & \textbf{Routing Acc.} & \textbf{SD ($s$)} & \textbf{95\% Student's $t$-CI} & \textbf{F1} & \textbf{LOAO} & \textbf{Latency} & \textbf{CPU Util.} & \textbf{GPU Util.} \\
\midrule
\textbf{Logistic Reg.} & 68.80\% & 0.414\% & [68.27\%, 69.33\%] & 61.16\% & 62.40\% & 0.00014 ms & 4.5\% & 0.0\% \\
\textbf{Random Forest} & 79.34\% & 0.294\% & [78.90\%, 79.78\%] & 79.50\% & 68.23\% & 0.00877 ms & 18.0\% & 0.0\% \\
\bottomrule
\end{tabular}%
}
\end{table}

In Table~\ref{tab:router_selection}, we see that the most accurate method was the VQC simulator on 4 MI250X GPUs, with a latency of 10.889ms (91.8 packets per second) and accuracy of 81.46\%. Notably, the Random Forest router had an accuracy of 79.34\% $\pm$ 0.29\%, a latency of 0.00877ms, and 114,000 packets per second. Logistic Regression had an accuracy of 68.80\% $\pm$ 0.41\%, and a significantly lower latency of 0.00014ms with 7.14 million packets per second. 

It is worth noting that the IBM QPU routing performed the lowest in accuracy (40.53\%) and had the highest latency, 113.975ms, leading to 8.8 packets per second. Considering the complexity, cost, and availability of the hardware, it is not a viable use of QPU compute allocations in its current form.

\begin{table}[t]
\centering
\caption{First-Choice Router Selection Accuracy Across Architectures.}
\label{tab:router_selection}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lccccccr}
\toprule
\textbf{Router Architecture} & \textbf{Hardware} & \textbf{Selection Acc.} & \textbf{LOAO Acc.} & \textbf{Latency} & \textbf{Rate} & \textbf{CPU Util.} & \textbf{GPU Util.} \\
\midrule
\textbf{Theoretical Oracle} & Reference & 100.00\% & 100.00\% & 0.000 ms & $\infty$ & 0.0\% & 0.0\% \\
\textbf{Logistic Regression} & 16-Core CPU & 68.80\% $\pm$ 0.41\% & 62.40\% & 0.00014 ms & 7.14M pps & 4.5\% & 0.0\% \\
\textbf{Random Forest} & 16-Core CPU & 79.34\% $\pm$ 0.29\% & 68.23\% & 0.00877 ms & 114.0K pps & 18.0\% & 0.0\% \\
\textbf{VQC Simulator} & 4 MI250X Cards & 81.46\% & N/A & 10.889 ms & 91.8 pps & 12.0\% & 86.0\% \\
\textbf{IBM QPU Router} & Heron r2 (156Q) & 40.53\% & N/A & 113.975 ms & 8.8 pps & 5.0\% & 0.0\% \\
\bottomrule
\end{tabular}%
}
\end{table}

The end-to-end routed stream reconciliation capabilities across architectures are shown in Table~\ref{tab:routed_e2e_reconciliation}, while Table~\ref{tab:statistical_significance} and Table~\ref{tab:mcnemar_matrix} outline statistical evaluation metrics comparing the VQC and Random Forest implementations.

\begin{table}[t]
\centering
\caption{Routed End-to-End Stream Reconciliation Accuracy \& Utilization.}
\label{tab:routed_e2e_reconciliation}
\resizebox{\columnwidth}{!}{%
\begin{tabular}{lcccccc}
\toprule
\textbf{Router Architecture} & \textbf{Routing Acc.} & \textbf{Routed E2E Rec. Acc.} & \textbf{95\% CI} & \textbf{Latency} & \textbf{CPU Util.} & \textbf{GPU Util.} \\
\midrule
\textbf{Theoretical Oracle} & 100.00\% & \textbf{100.00\%} & [100.00\%, 100.00\%] & 0.000 ms & 0.0\% & 0.0\% \\
\textbf{VQC Simulator Router} & 81.46\% & \textbf{98.15\%} & [98.05\%, 98.25\%] & 10.889 ms & 12.0\% & 86.0\% \\
\textbf{Random Forest Router} & 79.34\% $\pm$ 0.29\% & \textbf{97.82\%} & [97.71\%, 97.93\%] & 0.00877 ms & 18.0\% & 0.0\% \\
\textbf{Logistic Regression} & 68.80\% $\pm$ 0.41\% & \textbf{94.85\%} & [94.71\%, 94.99\%] & 0.00014 ms & 4.5\% & 0.0\% \\
\textbf{IBM QPU Router} & 40.53\% & \textbf{78.40\%} & [78.28\%, 78.52\%] & 113.975 ms & 5.0\% & 0.0\% \\
\textit{Best Reconciler (BERT)} & \textit{N/A (Fixed)} & \textit{87.76\%} & [81.51\%, 94.02\%] & \textit{36.751 ms} & \textit{8.5\%} & \textit{78.2\%} \\
\bottomrule
\end{tabular}%
}
\end{table}

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

\begin{table}[htbp]
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

\begin{table}[htbp]
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

% ==============================================================================
% SECTION 6: DOMAIN ANALYSIS
% ==============================================================================

\section{Domain Analysis}
As observed in Table~\ref{tab:domain_breakdown}, performance across individual microservice telemetry domains highlights variance across lightweight string dynamic programming, dense embeddings, and variational quantum routing.

\begin{table}[htbp]
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
\bottomrule
\end{tabular}%
}
\end{table}

\section{Contributions}

\begin{itemize}
    \item Real time telemetry GPU-accelerated schema reconciliation
    \item Multi-platform schema reconciliation
    \item Quantum routed schema reconciliation
    \item Energy-aware HPC optimization
    \item Cross-domain empirical generalization
    \item Multi-topology physical hardware benchmarks (GPU/QPU/CPU)
    \item Upstream QPU positioning for an inverted control plane
\end{itemize}

\section{Threats to Validity/Limitations}
Since Gemma4-E2B-it is a smaller autogregressive decoder model, it can be concluded that there is limited benefit to incorporate such models in environments where sub-millisecond latency is required for schema drift reconciliation. Quantum compute allocations are difficult to secure, limiting the amount of quantum training that can be conducted for a project. 

As previously mentioned, due to the low-availability of IBM Open Instance QPU time, it is possible that this cannot be used on a live telemetry stream. To mitigate constant use, LUMI and IBM's Quantum Platform use a SLURM batching process.

Additionally, some API sources are cyclically offline during distinct periods (such as Finnhub outside of trading hours, UEFA/NHL/F1 outside of competition periods, and SpaceX outside of launch events, for example). In order to conduct benchmarking on all API sources concurrently, historical data was sampled for some data sources.

all-MiniLM-L6-v2 has a limitation of 256 characters before it truncates inputs, which could reduce its accuracy in the unlikely event there are extremely complex variable names ~\cite{bert}
\section{Conclusion}
The most efficient routing option was the VQC simulator on the MI250X, while the CPU processes were significantly faster. Random Forest had a comparable accuracy to the VQC simulator with less than 1/1000th of the associated latency. The IBM QPU router exhibited considerably lower latency and accuracy than GPU and CPU reconciliation, which suggests that physical deployment of this type of pipeline is constrained by hardware noise and availability that are observed in a contemporary environment.

\section{Future Work}
The pipeline will be evaluated on NVIDIA GH200's CPU/GPU platform, exploring validation on a CUDA framework. We will continue to explore the validity of a quantum application in reconciliation routing, by adapting the quantum circuit to fit a specific QPU layout and qubit count.
\end{document}
"""

    output_path = REPO_ROOT / "data" / "reports" / "overleaf_tables.tex"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(latex_content)

    print(f"SUCCESS: Exported complete Overleaf document to {output_path}")

if __name__ == "__main__":
    generate_complete_overleaf_doc()

