import re

print("Adding End-to-End Workflow & Triggered Scripts Guide to README.md...")

readme_path = "README.md"
content = open(readme_path).read()

workflow_sec = """---

## End-to-End Execution Workflow & Triggered Scripts

The Resilient RAP framework follows a 5-stage pipeline architecture from raw multi-domain stream ingestion to physical QPU execution and single-source report consolidation:

```mermaid
flowchart TD
    A[Stage 1: Multi-Domain Ingestion] --> B[Stage 2: Chaos Engineering & Perturbation]
    B --> C[Stage 3: Feature Extraction & Oracle Building]
    C --> D1[Stage 4a: Classical CPU Router Training]
    C --> D2[Stage 4b: VQC Aer GPU Simulation]
    C --> D3[Stage 4c: Physical IBM QPU Execution]
    D1 --> E[Stage 5: Master JSON Consolidation & Sync]
    D2 --> E
    D3 --> E
```

### Stage 1: Multi-Domain Telemetry Ingestion
Ingests real-world telemetry streams across 9 microservice APIs:
- **`scripts/ingest_openf1_historical.py`**: Ingests formula telemetry vector streams from OpenF1 API.
- **`scripts/ingest_finnhub_historical.py`**: Ingests high-frequency financial tick feeds from Finnhub API.
- **`scripts/ingest_spacex_historical.py`**: Ingests orbital launch telemetry streams from SpaceX API.
- **`scripts/ingest_openweather_historical.py`**: Ingests atmospheric vector streams from OpenWeather API.
- **`scripts/ingest_openfda.py`**: Ingests clinical adverse event records from OpenFDA API.
- **`scripts/generate_balanced_data.py`**: Synthesizes balanced 9-domain corpus (`data/ingested/*.json`).

### Stage 2: Chaos Engineering & Stream Perturbation
Applies 3 drift/chaos families without leaking packet identities across split boundaries:
- **`scripts/run_chaos_sweep.py`**: Executes perturbation generator across JSON structural drift (`json_manip`), Qwen LLM schema reformulation (`qwen`), and syntactic truncation/drift (`schema_alter`).
- **`run_matrix.py`**: Executes full cross-evaluation matrix across all 9 APIs, 3 drift families, and 6 candidate reconcilers.
- **Outputs**: `data/reports/*/matrix_results*.csv`.

### Stage 3: Feature Extraction & Cost-Aware Oracle Construction
Extracts 10 pre-reconciliation feature dimensions ($x_0, \\dots, x_9 \\in [0, \\pi]$) and establishes ground-truth oracle route labels:
- **`scripts/build_router_oracle.py`**: Evaluates all candidate reconcilers per packet and assigns cost-aware ground-truth optimal route labels across 31,500 packets (80% train, 10% val, 10% test).
- **`scripts/export_vqc_features_csv.py`**: Exports pre-extracted 10-dimensional feature vectors into CSV format for classical model training.
- **Outputs**: `data/training/router_oracle_22500_v2.manifest.json`, `data/training/router_oracle_22500_v2.workload.jsonl.gz`, `data/vqc_input_features_22500.csv`.

### Stage 4: Router Training & Multi-Architecture Evaluation
Trains and evaluates router models across classical CPU, GPU statevector simulator, and physical QPU hardware:
- **Classical CPU Router Baselines**:
  - **`scripts/run_classical_router_experiment.py`**: Trains Multinomial Logistic Regression and Random Forest models across 10 random seeds ($80/10/10$ packet-identity splits) and Leave-One-API-Out (LOAO) cross-validation.
  - **Outputs**: `data/reports/classical_router_benchmark_results.json`.
- **VQC Simulator Router (Aer GPU)**:
  - **`scripts/train_router.py`**: Trains 12-qubit Variational Quantum Classifier (`ZZFeatureMap` + `RealAmplitudes` ansatz) on AMD Instinct MI250X GPUs.
  - **`scripts/run_gpu_scalability_sweep.py`**: Benchmarks GPU execution throughput and scaling across 1 vs. 4 MI250X cards.
- **Physical IBM QPU Router**:
  - **`scripts/run_qpu_router_experiment.py`**: Constructs 12-qubit VQC circuits for IBM Quantum execution.
  - **`scripts/submit_shadow_qpu.py`**: Submits 20,250 circuits (7.776M physical QPU executions) to IBM Heron r2 (`ibm_marrakesh`).
  - **`scripts/fetch_qpu_results.py`**: Retrieves physical QPU execution results for Job `d9idh9d0k0jc738jf4ug`.
- **Cloud Dense Vector Baseline**:
  - **`scripts/run_cohere_benchmark.py`**: Benchmarks Cohere `embed-english-v3.0` API dense vector representation baseline.

### Stage 5: Master Report Consolidation & Documentation Sync
Ensures 100% internal consistency between benchmark artifacts and repository documentation:
- **`scripts/generate_master_results_json.py`**: Programmatically computes arithmetic macro-averages and consolidates global summaries, per-API breakdowns, chaos matrix tables, classical router CIs, and QPU execution metadata into a single master JSON artifact.
- **`scripts/sync_readme_from_master_json.py`**: Programmatically verifies and syncs all README performance tables directly from the master JSON.
- **Outputs**: `data/reports/master_benchmark_results.json`, `README.md`."""

# Insert after Hardware Execution Environments section
target_anchor = "## Hardware Execution Environments"
if target_anchor in content:
    # Find the end of Hardware Execution Environments section (next '---')
    idx = content.find(target_anchor)
    next_dash = content.find("\n---\n", idx)
    if next_dash != -1:
        content = content[:next_dash] + "\n" + workflow_sec + content[next_dash:]

with open(readme_path, "w") as f:
    f.write(content)

print("SUCCESS: Added End-to-End Execution Workflow & Triggered Scripts section to README.md!")
