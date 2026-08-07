# Legacy & Archived Experiments Archive

This document archives historical, preliminary, and pre-calibration experimental runs for the Resilient RAP Framework. All publication-facing results in the main `README.md` derive strictly from the current master benchmark artifacts (`data/reports/master_benchmark_results.json`).

---

## 1. Archived Physical QPU Execution Sweeps (`ibm_fez`)

Prior to locking the production single-PUB submission protocol on **IBM Heron r2** (`ibm_marrakesh`), preliminary benchmarking sweeps were conducted across multi-job batch submissions on `ibm_fez` (156 qubits):

* **Backend Evaluated**: `ibm_fez` (IBM Heron r2, 156 Physical Qubits)
* **Job Allocation Strategy**: Multi-job batch sweep (27 individual PUB jobs)
* **Status**: Superceded by single-PUB consolidated submission (`d9idh9d0k0jc738jf4ug` on `ibm_marrakesh`).
* **Archived Artifact Location**: `archive/legacy_qpu_sweeps/`

---

## 2. Legacy Latency Claims & Hardware Profiling

* **Legacy Latency Claim (0.0156 ms)**: Early hardware profiling reports derived an artificial per-GPU / per-qubit latency multiplier ($0.0156 \text{ ms/packet}$). This metric was retired in favor of end-to-end wall-clock latency per packet and batch-normalized physical QPU walltime.
* **4-Reconciler Initial Baseline Setup**: Initial preliminary sweeps evaluated only 4 reconcilers (Levenshtein, Regex, BERT, Gemma). The production benchmark was expanded to 6 reconcilers (adding BGE Embedding and Cohere Embed).

---

## 3. Retired Carbon & Power Claims

* **Energy & Carbon Offset Profiling**: CodeCarbon power tracking tools remain in the codebase as an optional developer capability (`src/utils/energy_tracker.py`), but energy/carbon metrics are excluded from public paper performance tables to focus on latency, accuracy, and system throughput.
