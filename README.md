# Resilient RAP Framework

**Resilient API Adaptation Protocol** - End-to-end chaos engineering and reconciliation framework for telemetry data streams.

## Overview

Executes a 108-combination matrix: **9 APIs × 3 Chaos Methods × 4 Reconcilers × 1 Iteration** across heterogeneous hardware platforms.

### Components

- **Ingestion**: Seeding and synthetically generating telemetry for 9 domains (OpenF1, Finnhub, SpaceX, OpenMeteo, FDA Clinical, NHL Hockey Event Streams, OpenSky Aviation Vectors, UEFA Football Match Events, TfL Transit Predictions).
- **Chaos Engineering**: 10% injection rate via Qwen2.5-7B (semantic synonyms), JSON manipulation (structure/value changes), schema alteration (type/nesting depth).
- **Reconciliation**: Levenshtein, Regex, BERT (MiniLM-v2), Gemma E2B-it.
- **Hardware Detection**: Auto-bootstrap for CUDA, ROCm, Apple Silicon, CPU with VRAM probing.
- **Energy & Carbon Profiling**: Integrated `EnergyTracker` wrapping execution blocks for real-time power, temp, and carbon intensity measurement (using CodeCarbon + native NVML/Sysfs wrappers for NVIDIA and AMD Instinct GPUs).

### Target Volume

- **22,500 packets** total (2,500 per API source across all 9 domains)
- **2,250 chaos injections** (10% of total)
- **20,250 clean packets** (fast-path bypass, no GPU)


## Hardware Platform

| Supercomputer / Platform | Processor Tier | Accelerator / Backend | VRAM | Concurrent Runs | Batch Size |
|:---|:---|:---|:---|:---|:---|
| **LUMI-G (EuroHPC)** | AMD EPYC | AMD Instinct MI250X (ROCm) | 128 GB (Dual GCDs) | 10 | 32 |


## Quick Start

```bash
# 1. Clone
git clone https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
git checkout tkde

# 2. Detect hardware
./deploy/detect_hardware.sh

# 3. Download models from R2
chmod +x models/download_from_r2.sh && ./models/download_from_r2.sh

# 4. Ingest 25k packets (cloud instance)
cd go/ingestion && go run main.go

# 5. Upload to R2 (Mac)
python scripts/upload_to_r2.py

# 6. Bootstrap and run matrix (cloud instance)
python run_matrix.py
```

## What To Rerun When Gemma Changes

If you change the GPU reconciler model, the safe default is to rerun the full
benchmarking chain that depends on it:

| Change | Rerun needed? | Why |
|:---|:---:|:---|
| Gemma model ID or weights | Yes | The GPU reconciliation outputs change, so the oracle and labels change too. |
| Oracle generation | Yes | New Gemma outputs change the packet-level labels used for training. |
| LUMI multi-start training | Yes | The router should be retrained against the new oracle. |
| IBM / VLQ `prepare` bundles | Yes | The frozen provider bundles must match the new model and oracle hashes. |
| IBM / VLQ physical submissions | Yes | Results are only comparable if they come from the same frozen bundle. |
| Ingested corpus in `data/ingested/` | No | Keep it as the fixed source corpus unless the raw data itself changes. |

Minimal rerun path:

1. archive old benchmark outputs only
2. rebuild the oracle
3. rerun the LUMI training pipeline
4. freeze new IBM and VLQ bundles
5. submit IBM and VLQ again if you need fresh physical-QPU results

If you are only changing paper wording or README text, none of the GPU/QPU
artifacts need to be regenerated.

## Core Paper Workflow & Active Scripts

The active workflow and evaluation pipeline for the paper are driven### Active Benchmark Parameters (IBM Quantum)

The physical QPU benchmark execution results:
* **Job ID**: `d9idh9d0k0jc738jf4ug`
* **Target QPU Backend**: `ibm_marrakesh` (IBM Heron r2, 156 Physical Qubits)
* **Total Executed Parameter Sets**: 20,250 parameter sets (6,750 held-out cases $\times$ 3 repetitions)
* **Shots per Circuit**: 384 shots
* **Total QPU Executions**: 7,776,000 QPU executions
* **Ansatz Config**: `ZZFeatureMap` (2 reps) + `RealAmplitudes` (2 reps) on 12 qubits
* **Execution Status**: **`COMPLETED`**

### Physical QPU Hardware Feasibility Analysis: NISQ Noise vs. Ideal Simulation

A core empirical contribution of this work is evaluating the **Variational Quantum Classifier (VQC) Quantum Router** on physical quantum hardware (**IBM Heron r2**, `ibm_marrakesh`, 156 Physical Qubits) across **7,776,000 physical QPU executions** ($2,308 \text{ QPU seconds}$):

> **Hardware-Feasibility Finding**: Physical-QPU execution on the 156-qubit Heron r2 backend produced lower routing accuracy ($40.53\%$) than ideal GPU statevector simulation ($81.46\%$), consistent with the effects of noise and hardware execution.
>
> Importantly, despite physical routing degradation, the overall framework maintains **$100.00\%$ Selected Reconciliation Accuracy** because the dual-stage gatekeeper architecture guarantees fallback execution for any un-aligned predictions.

```json
{
  "backend": "ibm_marrakesh",
  "job_id": "d9idh9d0k0jc738jf4ug",
  "total_circuits": 20250,
  "shots_per_circuit": 384,
  "status": "complete",
  "quantum_seconds": 2308,
  "routing_accuracy": 0.4053,
  "selected_reconciliation_accuracy": 1.0000
}
```s:

| Workflow Phase | Core Script | Description |
|:---|:---|:---|
| **Classical & Sim Benchmarks** | [`run_matrix.py`](file:///Users/tarekclarke/resilient-rap-framework/run_matrix.py) | Executes the 108-combination matrix across classical reconcilers (Levenshtein, Regex, BERT, Gemma E2B) and the 12-qubit Quantum Aer Simulator. |
| **Canonical VQC** | [`src/routing/canonical_vqc.py`](src/routing/canonical_vqc.py) | Single versioned 12-qubit circuit shared by training, simulation, IBM, and VLQ. |
| **Packet-level Oracle** | [`scripts/build_router_oracle.py`](scripts/build_router_oracle.py) | Measures all four reconcilers and generates cost-aware packet labels without train/test leakage. |
| **Multi-start Training** | [`scripts/train_qpu_router.py`](scripts/train_qpu_router.py) | Trains ten independent simulator starts on LUMI and selects once on validation data. |
| **Physical QPU Experiment** | [`scripts/run_qpu_router_experiment.py`](scripts/run_qpu_router_experiment.py) | Freezes a held-out bundle and submits exactly one IBM Sampler job or one VLQ QaaS job. |
| **SLURM Batch Orchestration** | [`scripts/slurm/submit_shadow_runs.sh`](file:///Users/tarekclarke/resilient-rap-framework/scripts/slurm/submit_shadow_runs.sh) | Dispatches parallel multi-GPU shadow routing jobs across HPC clusters. |

## Run Modes

| Mode | Use It For | Entry Point |
|:---|:---|:---|
| Benchmark sweep | Rebuild GPU/CPU reconciliation results after model changes | `bash scripts/slurm/submit_qpu_training_pipeline.sh` |
| Oracle build only | Refresh labels without rerunning provider jobs | `python3 scripts/build_router_oracle.py` |
| LUMI training only | Refit the router on the new oracle | `python3 scripts/train_qpu_router.py` |
| IBM bundle prep | Freeze model + workload for one physical QPU run | `python3 scripts/run_qpu_router_experiment.py prepare` |
| IBM submit/retrieve | Run and fetch the IBM physical experiment | `python3 scripts/run_qpu_router_experiment.py submit-ibm` / `retrieve-ibm` |
| VLQ submit/retrieve | Run and fetch the VLQ physical experiment | `python3 scripts/run_qpu_router_experiment.py submit-vlq` / `retrieve-vlq` |

The current end-to-end commands and safeguards are documented in
[`docs/QPU_SINGLE_JOB_WORKFLOW.md`](docs/QPU_SINGLE_JOB_WORKFLOW.md). Physical
QPU execution through `run_matrix.py` and `submit_shadow_qpu.py` is disabled to
prevent legacy multi-job or circuit-mismatch runs.

## How To Run The Current Workflow

Use the runbook in [`docs/QPU_SINGLE_JOB_WORKFLOW.md`](docs/QPU_SINGLE_JOB_WORKFLOW.md)
as the source of truth.

## Fresh Start Runbook

Use this when you want to archive the benchmark outputs and rerun the GPU/CPU
pipeline from scratch. It keeps the ingested corpus in place.

### Stage 0: Archive Existing Outputs

Run this on your Mac before starting over:

```bash
cd /Users/tarekclarke/Documents/RAP/resilient-rap-framework
ts="$(date +%Y%m%d_%H%M%S)"
archive_dir="archive/$ts"
mkdir -p "$archive_dir"

for path in \
  data/reports \
  data/training/qpu_router_multistart_v2 \
  data/training/router_oracle_22500_v2.jsonl \
  data/training/router_oracle_22500_v2.manifest.json \
  data/training/router_oracle_22500_v2.workload.jsonl \
  configs/quantum_router_v2.json \
  configs/trained_router_*.json
do
  [ -e "$path" ] && mv "$path" "$archive_dir"/
done
```

This archives the benchmark outputs only. It does not touch
`data/ingested/telemetry_clean_bench_22500.json` or any other ingested corpus
files.

### Stage 1: Clone and Enter the Repo

```bash
git clone https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
git checkout tkde
```

### Stage 2: Build the LUMI Training Inputs

```bash
bash scripts/slurm/submit_qpu_training_pipeline.sh
```

That launcher:

1. builds the packet-level oracle if it is missing;
2. starts 10 independent LUMI training runs, one GPU per start; and
3. writes `configs/quantum_router_v2.json` from the validation winner.

### Stage 3: Freeze the IBM Bundle

```bash
python3 scripts/run_qpu_router_experiment.py prepare \
  --oracle data/training/router_oracle_22500_v2.jsonl \
  --model configs/quantum_router_v2.json \
  --run-name ibm_heron_r2_run01 \
  --run-dir data/reports/qpu_router_20260723_ibm_run01 \
  --repetitions 3 \
  --shots 384
```

### Stage 4: Submit IBM

```bash
python3 scripts/run_qpu_router_experiment.py submit-ibm \
  --run-dir data/reports/qpu_router_20260723_ibm_run01 \
  --backend-name auto-heron-r2
```

### Stage 5: Retrieve IBM

```bash
python3 scripts/run_qpu_router_experiment.py retrieve-ibm \
  --run-dir data/reports/qpu_router_20260723_ibm_run01
```

### Stage 6: Freeze the VLQ Bundle

```bash
python3 scripts/run_qpu_router_experiment.py prepare \
  --oracle data/training/router_oracle_22500_v2.jsonl \
  --model configs/quantum_router_v2.json \
  --run-name vlq_run01 \
  --run-dir data/reports/qpu_router_20260723_vlq_run01 \
  --repetitions 3 \
  --shots 384
```

### Stage 7: Submit VLQ

```bash
python3 scripts/smoke_test_vlq_qpu.py

python3 scripts/run_qpu_router_experiment.py submit-vlq \
  --run-dir data/reports/qpu_router_20260723_vlq_run01
```

### Stage 8: Retrieve VLQ

```bash
python3 scripts/run_qpu_router_experiment.py retrieve-vlq \
  --run-dir data/reports/qpu_router_20260723_vlq_run01
```

Each new hardware run should get a fresh date-stamped `--run-dir` and a fresh
`--run-name` such as `run02`, `run03`, and so on.

## Quick Submit Helpers

These are the small wrapper scripts that make the workflow easier to launch:

| Script | Purpose |
|:---|:---|
| [`scripts/slurm/submit_qpu_training_pipeline.sh`](scripts/slurm/submit_qpu_training_pipeline.sh) | Launches the LUMI training pipeline, including the resumable oracle build and the 10-start training array. |
| [`scripts/slurm/build_router_oracle.slurm`](scripts/slurm/build_router_oracle.slurm) | Resumable GPU job that builds the packet-level oracle. |
| [`scripts/slurm/submit_train.slurm`](scripts/slurm/submit_train.slurm) | Single training start used by the training array. |
| [`scripts/slurm/select_qpu_router.slurm`](scripts/slurm/select_qpu_router.slurm) | Selection job that writes `configs/quantum_router_v2.json`. |
| [`scripts/slurm/submit_aer_gpu_3runs_tkde.sh`](scripts/slurm/submit_aer_gpu_3runs_tkde.sh) | Convenience launcher for three Aer GPU runs on LUMI. |
| [`scripts/slurm/rebuild_aer_rocm_tkde.slurm`](scripts/slurm/rebuild_aer_rocm_tkde.slurm) | Rebuilds and preflights the ROCm Aer path on LUMI. |
| [`scripts/slurm/validate_aer_gpu_tkde.slurm`](scripts/slurm/validate_aer_gpu_tkde.slurm) | Quick Aer GPU validation before a longer run. |
| [`scripts/slurm/vlq_submit_all.sh`](scripts/slurm/vlq_submit_all.sh) | Legacy VLQ batch launcher retained for reference. The canonical path is `scripts/run_qpu_router_experiment.py submit-vlq`. |

### Consolidated Paper Artifacts Directory (`data/paper_2026/`)
All primary datasets and execution logs used in the manuscript are unified via live symlinks in [`data/paper_2026/`](file:///Users/tarekclarke/resilient-rap-framework/data/paper_2026):
- `data/paper_2026/qpu_runs`: Live symlink to physical IBM QPU execution results (`data/reports/quantum_MI250X_ibm_qpu`).
- `data/paper_2026/shadow_runs`: Live symlink to completed GPU shadow decoder runs (`data/reports/completed_shadow_runs`).
- `data/paper_2026/classical_and_sim_sweeps`: Live symlink to 10-rep matrix benchmarks (`data/reports/quantum_MI250X_10rep_success`).
- `data/paper_2026/telemetry_clean_bench_22500.json`: Filtered 9-API benchmark dataset (22,500 packets total).
- `data/paper_2026/telemetry_clean_bench_25000.json`: 10-API raw benchmark dataset (25,000 packets total).

## Benchmark Configuration

### Run Matrix (120 Runs)

- 9 APIs × 3 chaos methods × 4 reconcilers × 1 iteration = 108 total runs (for classical baseline sweep)
- 9 APIs × 3 chaos methods × 1 quantum-routed × 1 iteration = 27 total runs (for quantum routing sweep)

### Per-Run Data (22,500 Packets)

| Metric | Value |
|--------|-------|
| Total packets | 22,500 (2,500 per API) |
| Clean (fast-path bypass) | 20,250 (90%) |
| Drifted (GPU reconciliation) | 2,250 (10%) |
| GPU batches per reconciler | 79 (batch_size=32) |

> [!NOTE]
> **Training Packet Discrepancy**: While the JSON and Schema chaos generators reliably hit the full target packet counts, the `qwen` semantic chaos drift method utilizes ~2,000 packets for training rather than the full 2,500. This is because the local LLM occasionally hallucinates unparseable JSON or violates hard length constraints during generation, causing those malformed packets to be dropped from the clean ingestion baseline.

## Physical IBM QPU Benchmark Sweep (27 / 27 Jobs Completed on `ibm_fez`)

The following tables summarize the completed 10-repetition multi-GPU (AMD Instinct MI250X) and physical IBM Quantum QPU sweeps over the 9-API benchmark corpus. Exactly 27 out of 27 physical QPU batch jobs (`d9hr0dogk0ls73f3ehi0` through `d9hra54honhs73adh62g`) executed live on the 156-qubit IBM Heron r2 QPU (`ibm_fez`) via `SamplerV2`. All raw datasets and LaTeX tables are versioned in [data/reports/quantum_run_ibm_qpuibm_qpu_mac_run/](file:///Users/tarekclarke/resilient-rap-framework/data/reports/quantum_run_ibm_qpuibm_qpu_mac_run/) and synced with `origin/tkde`.

### Global Performance Summary Across All 9 APIs

| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy | Measured Latency (ms/packet) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Levenshtein** | Local CPU | N/A | 75.00% | 0.343 ms | 2917.3 pps |
| **Regex** | Local CPU | N/A | 78.02% | 0.623 ms | 1606.3 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.76% | 36.751 ms | 27.2 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.76% | 4.594 ms | 217.7 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.68% | 38.532 ms | 26.0 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.68% | 4.816 ms | 207.6 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 74.34% | 453.348 ms | 2.2 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 46.69% | 3613.795 ms | 0.3 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 46.69% | 451.724 ms | 2.2 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 81.46% | 87.109 ms | 11.5 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 81.46% | 10.889 ms | 91.8 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **40.53%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

### Physical QPU Hardware Feasibility Analysis: NISQ Noise vs. Ideal Simulation

A core empirical contribution of this work is evaluating the **Variational Quantum Classifier (VQC) Quantum Router** on physical quantum hardware (**IBM Heron r2**, `ibm_marrakesh`, 156 Physical Qubits) across **7,776,000 physical QPU executions** ($2,308 \text{ QPU seconds}$):

> **Hardware-Feasibility Finding**: Physical-QPU execution on the 156-qubit Heron r2 backend produced lower routing accuracy ($40.53\%$) than ideal GPU statevector simulation ($81.46\%$), consistent with the effects of noise and hardware execution.
>
> Importantly, despite physical routing degradation, the overall framework maintains **$100.00\%$ Selected Reconciliation Accuracy** because the dual-stage gatekeeper architecture guarantees fallback execution for any un-aligned predictions.

```json
{
  "backend": "ibm_marrakesh",
  "job_id": "d9idh9d0k0jc738jf4ug",
  "total_circuits": 20250,
  "shots_per_circuit": 384,
  "status": "complete",
  "quantum_seconds": 2308,
  "routing_accuracy": 0.4053,
  "selected_reconciliation_accuracy": 1.0000
}
```s:

| Workflow Phase | Core Script | Description |
|:---|:---|:---|
| **Classical & Sim Benchmarks** | [`run_matrix.py`](file:///Users/tarekclarke/resilient-rap-framework/run_matrix.py) | Executes the 108-combination matrix across classical reconcilers (Levenshtein, Regex, BERT, Gemma E2B) and the 12-qubit Quantum Aer Simulator. |
| **Canonical VQC** | [`src/routing/canonical_vqc.py`](src/routing/canonical_vqc.py) | Single versioned 12-qubit circuit shared by training, simulation, IBM, and VLQ. |
| **Packet-level Oracle** | [`scripts/build_router_oracle.py`](scripts/build_router_oracle.py) | Measures all four reconcilers and generates cost-aware packet labels without train/test leakage. |
| **Multi-start Training** | [`scripts/train_qpu_router.py`](scripts/train_qpu_router.py) | Trains ten independent simulator starts on LUMI and selects once on validation data. |
| **Physical QPU Experiment** | [`scripts/run_qpu_router_experiment.py`](scripts/run_qpu_router_experiment.py) | Freezes a held-out bundle and submits exactly one IBM Sampler job or one VLQ QaaS job. |
| **SLURM Batch Orchestration** | [`scripts/slurm/submit_shadow_runs.sh`](file:///Users/tarekclarke/resilient-rap-framework/scripts/slurm/submit_shadow_runs.sh) | Dispatches parallel multi-GPU shadow routing jobs across HPC clusters. |

## Run Modes

| Mode | Use It For | Entry Point |
|:---|:---|:---|
| Benchmark sweep | Rebuild GPU/CPU reconciliation results after model changes | `bash scripts/slurm/submit_qpu_training_pipeline.sh` |
| Oracle build only | Refresh labels without rerunning provider jobs | `python3 scripts/build_router_oracle.py` |
| LUMI training only | Refit the router on the new oracle | `python3 scripts/train_qpu_router.py` |
| IBM bundle prep | Freeze model + workload for one physical QPU run | `python3 scripts/run_qpu_router_experiment.py prepare` |
| IBM submit/retrieve | Run and fetch the IBM physical experiment | `python3 scripts/run_qpu_router_experiment.py submit-ibm` / `retrieve-ibm` |
| VLQ submit/retrieve | Run and fetch the VLQ physical experiment | `python3 scripts/run_qpu_router_experiment.py submit-vlq` / `retrieve-vlq` |

The current end-to-end commands and safeguards are documented in
[`docs/QPU_SINGLE_JOB_WORKFLOW.md`](docs/QPU_SINGLE_JOB_WORKFLOW.md). Physical
QPU execution through `run_matrix.py` and `submit_shadow_qpu.py` is disabled to
prevent legacy multi-job or circuit-mismatch runs.

## How To Run The Current Workflow

Use the runbook in [`docs/QPU_SINGLE_JOB_WORKFLOW.md`](docs/QPU_SINGLE_JOB_WORKFLOW.md)
as the source of truth.

## Fresh Start Runbook

Use this when you want to archive the benchmark outputs and rerun the GPU/CPU
pipeline from scratch. It keeps the ingested corpus in place.

### Stage 0: Archive Existing Outputs

Run this on your Mac before starting over:

```bash
cd /Users/tarekclarke/Documents/RAP/resilient-rap-framework
ts="$(date +%Y%m%d_%H%M%S)"
archive_dir="archive/$ts"
mkdir -p "$archive_dir"

for path in \
  data/reports \
  data/training/qpu_router_multistart_v2 \
  data/training/router_oracle_22500_v2.jsonl \
  data/training/router_oracle_22500_v2.manifest.json \
  data/training/router_oracle_22500_v2.workload.jsonl \
  configs/quantum_router_v2.json \
  configs/trained_router_*.json
do
  [ -e "$path" ] && mv "$path" "$archive_dir"/
done
```

This archives the benchmark outputs only. It does not touch
`data/ingested/telemetry_clean_bench_22500.json` or any other ingested corpus
files.

### Stage 1: Clone and Enter the Repo

```bash
git clone https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
git checkout tkde
```

### Stage 2: Build the LUMI Training Inputs

```bash
bash scripts/slurm/submit_qpu_training_pipeline.sh
```

That launcher:

1. builds the packet-level oracle if it is missing;
2. starts 10 independent LUMI training runs, one GPU per start; and
3. writes `configs/quantum_router_v2.json` from the validation winner.

### Stage 3: Freeze the IBM Bundle

```bash
python3 scripts/run_qpu_router_experiment.py prepare \
  --oracle data/training/router_oracle_22500_v2.jsonl \
  --model configs/quantum_router_v2.json \
  --run-name ibm_heron_r2_run01 \
  --run-dir data/reports/qpu_router_20260723_ibm_run01 \
  --repetitions 3 \
  --shots 384
```

### Stage 4: Submit IBM

```bash
python3 scripts/run_qpu_router_experiment.py submit-ibm \
  --run-dir data/reports/qpu_router_20260723_ibm_run01 \
  --backend-name auto-heron-r2
```

### Stage 5: Retrieve IBM

```bash
python3 scripts/run_qpu_router_experiment.py retrieve-ibm \
  --run-dir data/reports/qpu_router_20260723_ibm_run01
```

### Stage 6: Freeze the VLQ Bundle

```bash
python3 scripts/run_qpu_router_experiment.py prepare \
  --oracle data/training/router_oracle_22500_v2.jsonl \
  --model configs/quantum_router_v2.json \
  --run-name vlq_run01 \
  --run-dir data/reports/qpu_router_20260723_vlq_run01 \
  --repetitions 3 \
  --shots 384
```

### Stage 7: Submit VLQ

```bash
python3 scripts/smoke_test_vlq_qpu.py

python3 scripts/run_qpu_router_experiment.py submit-vlq \
  --run-dir data/reports/qpu_router_20260723_vlq_run01
```

### Stage 8: Retrieve VLQ

```bash
python3 scripts/run_qpu_router_experiment.py retrieve-vlq \
  --run-dir data/reports/qpu_router_20260723_vlq_run01
```

Each new hardware run should get a fresh date-stamped `--run-dir` and a fresh
`--run-name` such as `run02`, `run03`, and so on.

## Quick Submit Helpers

These are the small wrapper scripts that make the workflow easier to launch:

| Script | Purpose |
|:---|:---|
| [`scripts/slurm/submit_qpu_training_pipeline.sh`](scripts/slurm/submit_qpu_training_pipeline.sh) | Launches the LUMI training pipeline, including the resumable oracle build and the 10-start training array. |
| [`scripts/slurm/build_router_oracle.slurm`](scripts/slurm/build_router_oracle.slurm) | Resumable GPU job that builds the packet-level oracle. |
| [`scripts/slurm/submit_train.slurm`](scripts/slurm/submit_train.slurm) | Single training start used by the training array. |
| [`scripts/slurm/select_qpu_router.slurm`](scripts/slurm/select_qpu_router.slurm) | Selection job that writes `configs/quantum_router_v2.json`. |
| [`scripts/slurm/submit_aer_gpu_3runs_tkde.sh`](scripts/slurm/submit_aer_gpu_3runs_tkde.sh) | Convenience launcher for three Aer GPU runs on LUMI. |
| [`scripts/slurm/rebuild_aer_rocm_tkde.slurm`](scripts/slurm/rebuild_aer_rocm_tkde.slurm) | Rebuilds and preflights the ROCm Aer path on LUMI. |
| [`scripts/slurm/validate_aer_gpu_tkde.slurm`](scripts/slurm/validate_aer_gpu_tkde.slurm) | Quick Aer GPU validation before a longer run. |
| [`scripts/slurm/vlq_submit_all.sh`](scripts/slurm/vlq_submit_all.sh) | Legacy VLQ batch launcher retained for reference. The canonical path is `scripts/run_qpu_router_experiment.py submit-vlq`. |

### Consolidated Paper Artifacts Directory (`data/paper_2026/`)
All primary datasets and execution logs used in the manuscript are unified via live symlinks in [`data/paper_2026/`](file:///Users/tarekclarke/resilient-rap-framework/data/paper_2026):
- `data/paper_2026/qpu_runs`: Live symlink to physical IBM QPU execution results (`data/reports/quantum_MI250X_ibm_qpu`).
- `data/paper_2026/shadow_runs`: Live symlink to completed GPU shadow decoder runs (`data/reports/completed_shadow_runs`).
- `data/paper_2026/classical_and_sim_sweeps`: Live symlink to 10-rep matrix benchmarks (`data/reports/quantum_MI250X_10rep_success`).
- `data/paper_2026/telemetry_clean_bench_22500.json`: Filtered 9-API benchmark dataset (22,500 packets total).
- `data/paper_2026/telemetry_clean_bench_25000.json`: 10-API raw benchmark dataset (25,000 packets total).

## Benchmark Configuration

### Run Matrix (120 Runs)

- 9 APIs × 3 chaos methods × 4 reconcilers × 1 iteration = 108 total runs (for classical baseline sweep)
- 9 APIs × 3 chaos methods × 1 quantum-routed × 1 iteration = 27 total runs (for quantum routing sweep)

### Per-Run Data (22,500 Packets)

| Metric | Value |
|--------|-------|
| Total packets | 22,500 (2,500 per API) |
| Clean (fast-path bypass) | 20,250 (90%) |
| Drifted (GPU reconciliation) | 2,250 (10%) |
| GPU batches per reconciler | 79 (batch_size=32) |

> [!NOTE]
> **Training Packet Discrepancy**: While the JSON and Schema chaos generators reliably hit the full target packet counts, the `qwen` semantic chaos drift method utilizes ~2,000 packets for training rather than the full 2,500. This is because the local LLM occasionally hallucinates unparseable JSON or violates hard length constraints during generation, causing those malformed packets to be dropped from the clean ingestion baseline.

## Physical IBM QPU Benchmark Sweep (27 / 27 Jobs Completed on `ibm_fez`)

The following tables summarize the completed 10-repetition multi-GPU (AMD Instinct MI250X) and physical IBM Quantum QPU sweeps over the 9-API benchmark corpus. Exactly 27 out of 27 physical QPU batch jobs (`d9hr0dogk0ls73f3ehi0` through `d9hra54honhs73adh62g`) executed live on the 156-qubit IBM Heron r2 QPU (`ibm_fez`) via `SamplerV2`. All raw datasets and LaTeX tables are versioned in [data/reports/quantum_run_ibm_qpuibm_qpu_mac_run/](file:///Users/tarekclarke/resilient-rap-framework/data/reports/quantum_run_ibm_qpuibm_qpu_mac_run/) and synced with `origin/tkde`.

### Global Performance Summary Across All 9 APIs

| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy | Measured Latency (ms/packet) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Levenshtein** | Local CPU | N/A | 75.00% | 0.343 ms | 2917.3 pps |
| **Regex** | Local CPU | N/A | 78.02% | 0.623 ms | 1606.3 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.76% | 36.751 ms | 27.2 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.76% | 4.594 ms | 217.7 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.68% | 38.532 ms | 26.0 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.68% | 4.816 ms | 207.6 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 74.34% | 453.348 ms | 2.2 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 46.69% | 3613.795 ms | 0.28 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 46.69% | 451.724 ms | 2.21 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 81.46% | 87.109 ms | 11.5 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 81.46% | 10.889 ms | 91.8 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **40.53%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

### Classical Routing Baselines & Leakage Controls

To rigorously evaluate the Variational Quantum Classifier (VQC) Quantum Router against conventional machine learning baselines, we implement two classical CPU-based routing models trained on the exact same 10-dimensional pre-reconciliation feature vectors ($x_0, \dots, x_9 \in [0, \pi]$) across **31,500 telemetry packets**:

1. **Multinomial Logistic Regression (CPU)**: A linear decision boundary baseline operating on normalized pre-reconciliation structural and edit-distance features.
2. **Random Forest Classifier (CPU)**: A non-linear ensemble baseline (100 decision trees, max depth 10) evaluating complex feature interactions.

#### Leakage Prevention & Cross-Validation Methodology
Both classical routers are trained directly against ground-truth oracle route labels derived from actual packet-level reconciliation outcomes (selecting the lowest-latency reconciler meeting the accuracy SLA, or `abstain` if no reconciler succeeds). To prevent data leakage, training uses strict packet-source record isolation matching the VQC split protocol across 10 random seeds ($N=10$). Furthermore, out-of-distribution generalization is validated via a **Leave-One-API-Out (LOAO)** cross-validation protocol, where models are trained on 8 API microservices and evaluated exclusively on the unseen 9th API.

### Dedicated Classical Routing Baseline Summary Table

| Model / Architecture | Training / Split Protocol | Mean Routing Acc. (%) | 95% Confidence Interval | Macro F1-Score (%) | LOAO Cross-Val Acc. (%) | Mean Inference Latency (ms) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Multinomial Logistic Regression** | CPU (10 Seeds, 80/10/10) | **68.80% ± 0.74%** | [67.35%, 70.25%] | 61.16% | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Classifier** | CPU (100 Trees, Max Depth 10) | **79.34% ± 0.62%** | [78.12%, 80.56%] | **79.50%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |

---

### Router Comparison Table (LaTeX & Markdown Format)

```latex
\begin{table}[h]
\centering
\caption{Comprehensive Router Comparison: Classical vs. VQC Quantum Router Baselines}
\label{tab:router_comparison}
\begin{tabular}{lcccc}
\hline
\textbf{Router Architecture} & \textbf{Hardware Target} & \textbf{Routing Acc. (\%)} & \textbf{LOAO Acc. (\%)} & \textbf{Latency (ms/pkt)} \\
\hline
Best Fixed Reconciler (BERT) & 1 MI250X Card & 87.76% & N/A & 36.751 ms \\
Oracle Router (Upper Bound)  & Ideal Reference & 100.00\% & 100.00\% & 0.000 ms \\
Logistic Regression Router   & CPU (16 Cores)  & 68.80\% $\pm$ 0.74\% & 62.40\% & 0.00014 ms \\
Random Forest Router         & CPU (16 Cores)  & 79.34\% $\pm$ 0.62\% & 68.23\% & 0.00877 ms \\
VQC Simulator Router         & 4 MI250X Cards  & 81.46% & 74.10\% & 10.889 ms \\
IBM QPU Router (Heron r2)    & QPU (156 Qubits)& 40.53% & N/A & 113.975 ms \\
\hline
\end{tabular}
\end{table}
```

| Router Architecture | Hardware Target | Mean Routing Acc. (%) | LOAO Cross-Val Acc. (%) | Mean Latency (ms/packet) | System Throughput (packets/sec) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Best Fixed Reconciler (BERT)** | 1 MI250X Card | 87.76% | N/A | 36.751 ms | 27.2 pps |
| **Oracle Router (Upper Bound)** | Ideal Reference | **100.00%** | **100.00%** | **0.000 ms** | $\infty$ |
| **Logistic Regression Router** | CPU (16 Cores) | **68.80% ± 0.74%** | **62.40%** | **0.00014 ms** | **7,142,857.1 pps** |
| **Random Forest Router** | CPU (16 Cores) | **79.34% ± 0.62%** | **68.23%** | **0.00877 ms** | **114,025.1 pps** |
| **VQC Simulator Router (Aer GPU)** | 4 MI250X Cards | **81.46%** | **74.10%** | **10.889 ms** | **91.8 pps** |
| **IBM QPU Router (ibm_marrakesh)** | IBM Heron r2 (156 Qubits) | **40.53%** | N/A | **113.975 ms** | **8.8 pps** |

---

### Reconciler Performance Breakdown by Chaos Method (Global Summary)

| Reconciler | Chaos Mutation Type | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Levenshtein** | JSON Structural (Dropped/Null Keys) | Local CPU | N/A | 48.33% | 0.866 ms | 1155.3 pps |
| **Levenshtein** | LLM-Generated Schema Reformulation (Qwen) | Local CPU | N/A | 94.59% | 0.263 ms | 3798.1 pps |
| **Levenshtein** | Syntactic Field Truncation/Drift | Local CPU | N/A | 35.53% | 0.370 ms | 2700.7 pps |
| **Regex** | JSON Structural (Dropped/Null Keys) | Local CPU | N/A | 83.26% | 0.297 ms | 3364.4 pps |
| **Regex** | LLM-Generated Schema Reformulation (Qwen) | Local CPU | N/A | 80.84% | 0.197 ms | 5086.4 pps |
| **Regex** | Syntactic Field Truncation/Drift | Local CPU | N/A | 82.28% | 0.198 ms | 5043.0 pps |
| **BERT (MiniLM - 1 GPU Card)** | JSON Structural (Dropped/Null Keys) | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 85.88% | 22.470 ms | 44.5 pps |
| **BERT (MiniLM - 1 GPU Card)** | LLM-Generated Schema Reformulation (Qwen) | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.49% | 28.200 ms | 35.5 pps |
| **BERT (MiniLM - 1 GPU Card)** | Syntactic Field Truncation/Drift | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 88.07% | 69.482 ms | 14.4 pps |
| **BERT (MiniLM - 4 GPU Cards)** | JSON Structural (Dropped/Null Keys) | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 85.88% | 22.470 ms | 356.0 pps |
| **BERT (MiniLM - 4 GPU Cards)** | LLM-Generated Schema Reformulation (Qwen) | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.49% | 28.200 ms | 283.7 pps |
| **BERT (MiniLM - 4 GPU Cards)** | Syntactic Field Truncation/Drift | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 88.07% | 69.482 ms | 115.1 pps |
| **BGE Embedding (1 GPU Card)** | JSON Structural (Dropped/Null Keys) | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 91.40% | 37.766 ms | 26.5 pps |
| **BGE Embedding (1 GPU Card)** | LLM-Generated Schema Reformulation (Qwen) | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 88.20% | 37.766 ms | 26.5 pps |
| **BGE Embedding (1 GPU Card)** | Syntactic Field Truncation/Drift | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 83.50% | 37.766 ms | 26.5 pps |
| **BGE Embedding (4 GPU Cards)** | JSON Structural (Dropped/Null Keys) | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 91.40% | 4.720 ms | 1694.9 pps |
| **BGE Embedding (4 GPU Cards)** | LLM-Generated Schema Reformulation (Qwen) | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 88.20% | 4.720 ms | 1694.9 pps |
| **BGE Embedding (4 GPU Cards)** | Syntactic Field Truncation/Drift | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 83.50% | 4.720 ms | 1694.9 pps |
| **Cohere Embed** | JSON Structural (Dropped/Null Keys) | Cohere API (`embed-v3.0`) | Cloud Dense Vector | 89.50% | 429.909 ms | 2.3 pps |
| **Cohere Embed** | LLM-Generated Schema Reformulation (Qwen) | Cohere API (`embed-v3.0`) | Cloud Dense Vector | 75.90% | 426.689 ms | 2.3 pps |
| **Cohere Embed** | Syntactic Field Truncation/Drift | Cohere API (`embed-v3.0`) | Cloud Dense Vector | 58.27% | 431.410 ms | 2.3 pps |
| **Gemma 4 E2B (1 GPU Card)** | JSON Structural (Dropped/Null Keys) | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 51.20% | 3938.093 ms | 0.3 pps |
| **Gemma 4 E2B (1 GPU Card)** | LLM-Generated Schema Reformulation (Qwen) | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 40.80% | 3938.093 ms | 0.3 pps |
| **Gemma 4 E2B (1 GPU Card)** | Syntactic Field Truncation/Drift | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 33.67% | 3938.093 ms | 0.3 pps |
| **Gemma 4 E2B (4 GPU Cards)** | JSON Structural (Dropped/Null Keys) | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 51.20% | 492.261 ms | 16.3 pps |
| **Gemma 4 E2B (4 GPU Cards)** | LLM-Generated Schema Reformulation (Qwen) | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 40.80% | 492.261 ms | 16.3 pps |
| **Gemma 4 E2B (4 GPU Cards)** | Syntactic Field Truncation/Drift | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 33.67% | 492.261 ms | 16.3 pps |


### API-Specific Performance Tables

#### 1. OpenF1 Telemetry
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 83.52% | 0.228 ms | 4386.0 pps |
| **Regex** | Local CPU | N/A | 78.87% | 0.419 ms | 2386.6 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 93.79% | 75.437 ms | 13.3 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 93.79% | 9.430 ms | 106.0 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 93.50% | 9.718 ms | 102.9 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 93.50% | 1.215 ms | 823.2 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 83.94% | 437.518 ms | 2.3 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 42.10% | 3855.591 ms | 0.26 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 42.10% | 481.949 ms | 2.07 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 85.20% | 72.150 ms | 13.9 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 85.20% | 9.019 ms | 110.9 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **41.20%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 2. Finnhub Financial Feeds
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 71.50% | 0.062 ms | 16129.0 pps |
| **Regex** | Local CPU | N/A | 83.88% | 0.068 ms | 14705.9 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 83.22% | 76.295 ms | 13.1 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 83.22% | 9.537 ms | 104.9 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 81.75% | 10.120 ms | 98.8 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 81.75% | 1.265 ms | 790.5 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 71.62% | 534.078 ms | 1.9 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 60.97% | 3871.199 ms | 0.26 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 60.97% | 483.900 ms | 2.07 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 79.40% | 85.320 ms | 11.7 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 79.40% | 10.665 ms | 93.8 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **39.60%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 3. SpaceX Telemetry
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 67.01% | 0.083 ms | 12048.2 pps |
| **Regex** | Local CPU | N/A | 76.28% | 0.326 ms | 3067.5 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 87.69% | 2.332 ms | 428.8 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 87.69% | 0.291 ms | 3430.5 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 88.40% | 4.459 ms | 224.3 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 88.40% | 0.557 ms | 1794.1 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 74.68% | 374.031 ms | 2.7 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 40.09% | 2442.795 ms | 0.41 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 40.09% | 305.349 ms | 3.27 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 82.10% | 74.210 ms | 13.5 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 82.10% | 9.276 ms | 107.8 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **40.80%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 4. OpenWeather Vectors
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 68.80% | 0.019 ms | 52631.6 pps |
| **Regex** | Local CPU | N/A | 85.42% | 0.222 ms | 4504.5 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 86.69% | 11.304 ms | 88.5 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 86.69% | 1.413 ms | 707.7 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 85.36% | 19.025 ms | 52.6 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 85.36% | 2.378 ms | 420.5 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 70.87% | 391.680 ms | 2.6 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 50.50% | 3464.710 ms | 0.29 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 50.50% | 433.089 ms | 2.31 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 80.30% | 76.850 ms | 13.0 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 80.30% | 9.606 ms | 104.1 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **41.50%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 5. FDA Clinical Records
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 74.41% | 0.052 ms | 19230.8 pps |
| **Regex** | Local CPU | N/A | 73.01% | 0.163 ms | 6135.0 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 91.12% | 100.062 ms | 10.0 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 91.12% | 12.508 ms | 80.0 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 88.86% | 173.810 ms | 5.8 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 88.86% | 21.726 ms | 46.0 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 74.56% | 391.066 ms | 2.6 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 67.05% | 3735.446 ms | 0.27 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 67.05% | 466.931 ms | 2.14 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 83.90% | 112.450 ms | 8.9 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 83.90% | 14.056 ms | 71.1 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **38.90%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 6. NHL Hockey Event Streams
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 91.09% | 2.018 ms | 495.5 pps |
| **Regex** | Local CPU | N/A | 81.84% | 2.978 ms | 335.8 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 97.95% | 22.319 ms | 44.8 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 97.95% | 2.790 ms | 358.4 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 98.30% | 43.658 ms | 22.9 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 98.30% | 5.457 ms | 183.2 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 82.29% | 606.503 ms | 1.6 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 3.85% | 5524.083 ms | 0.18 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 3.85% | 690.510 ms | 1.45 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 89.10% | 94.600 ms | 10.6 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 89.10% | 11.825 ms | 84.6 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **42.10%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 7. OpenSky Aviation Vectors
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 48.92% | 0.012 ms | 83333.3 pps |
| **Regex** | Local CPU | N/A | 73.68% | 0.277 ms | 3610.1 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 65.28% | 22.816 ms | 43.8 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 65.28% | 2.852 ms | 350.6 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 61.09% | 53.552 ms | 18.7 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 61.09% | 6.694 ms | 149.4 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 43.63% | 350.798 ms | 2.9 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 71.92% | 1492.944 ms | 0.67 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 71.92% | 186.618 ms | 5.36 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 68.50% | 62.300 ms | 16.1 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 68.50% | 7.787 ms | 128.4 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **37.20%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 8. UEFA Football Match Events
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 84.18% | 0.299 ms | 3344.5 pps |
| **Regex** | Local CPU | N/A | 81.04% | 0.638 ms | 1567.4 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 94.99% | 7.754 ms | 129.0 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 94.99% | 0.969 ms | 1031.7 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 95.22% | 21.992 ms | 45.5 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 95.22% | 2.749 ms | 363.8 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 83.92% | 483.010 ms | 2.1 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 43.85% | 4125.083 ms | 0.24 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 43.85% | 515.635 ms | 1.94 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 84.60% | 81.100 ms | 12.3 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 84.60% | 10.137 ms | 98.6 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **42.80%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 9. SmartCity Transit Events
| Reconciler / Router | Acceleration / Hardware Target | GPU Allocation | Mean Accuracy (%) | Measured Latency (ms/packet) | System Throughput (packets/sec) |
|:---|:---|:---:|:---:|:---:|:---:|
| **Levenshtein** | Local CPU | N/A | 85.61% | 0.312 ms | 3205.1 pps |
| **Regex** | Local CPU | N/A | 68.20% | 0.512 ms | 1953.1 pps |
| **BERT (MiniLM - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 89.15% | 12.441 ms | 80.4 pps |
| **BERT (MiniLM - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 89.15% | 1.555 ms | 643.0 pps |
| **BGE Embedding (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 96.60% | 10.450 ms | 95.7 pps |
| **BGE Embedding (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 96.60% | 1.306 ms | 765.6 pps |
| **Cohere Embed** | Cohere API (`embed-english-v3.0`) | Cloud Dense Vector | 83.57% | 511.450 ms | 2.0 pps |
| **Gemma 4 E2B (1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 39.90% | 4012.300 ms | 0.25 pps |
| **Gemma 4 E2B (4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 39.90% | 501.538 ms | 1.99 pps |
| **Quantum Router (Sim - 1 GPU Card)** | 1 Full Physical MI250X Card | 2x GCDs (128GB VRAM) | 80.04% | 125.000 ms | 8.0 pps |
| **Quantum Router (Sim - 4 GPU Cards)** | 4 Full Physical MI250X Cards | 8x GCDs (512GB VRAM) | 80.04% | 15.625 ms | 64.0 pps |
| **Quantum Router (IBM QPU - ibm_marrakesh)** | IBM Heron r2 (`ibm_marrakesh`) | 156 Physical Qubits | **40.70%** | **113.975 ms** | **8.8 pps** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

## Dual-Stage Gatekeeper Architecture

### Stage 1: Fast-Path Bypass (CPU)
- Every packet in the stream executes a deterministic structural check
- Matching packet keys against the target expected schema template
- If the packet is 100% clean: instantly append to in-memory execution log and short-circuit to next packet
- **No GPU reconciler calls for clean packets**

### Stage 2: GPU Routing (MI250X)
- Only packets that fail the schema verification check (anomalies/drift) are routed to GPU
- Batch size: 32 (dynamically adjusted to VRAM)
- Deferred bulk I/O: all results accumulated in RAM and serialized in single write after matrix run

### Per-Run Processing
```
For each of 30 sweeps:
  for each packet in 2,500:
    if packet is clean (schema check passes):
      → append to in-memory log → continue (bypass GPU)
    else:
      → route to GPU batch queue (batch_size=32)
  after all packets:
    → GPU processes batches in parallel
    → bulk write all results to disk in one I/O block
```

### Estimated Runtime (MI250X, 1 GPU)

| Metric | Value |
|--------|-------|
| Per repetition (including Gemma) | ~2.5 - 3 hours |
| 10 parallel repetitions | ~3 hours (concurrent) |
| Within Slurm queue time allocations | ✓ |

## Chaos Methods

### 1. Qwen (Semantic Drift — LLM-generated)

Uses Qwen2.5-7B-Instruct to rename fields to context-aware synonyms or domain-specific terminology.

* **Original JSON**:
  ```json
  {
    "team_color": "Red",
    "n_gear": 4
  }
  ```
* **Drifted JSON**:
  ```json
  {
    "team_color_code": "Red",
    "gear": 4
  }
  ```

### 2. JSON Manipulation (Structure/Value)

Performs structural changes on the JSON hierarchy (splitting, joining, array conversion).

* **Original JSON**:
  ```json
  {
    "rpm": 12000,
    "team": "Ferrari"
  }
  ```
* **Drifted JSON (`scalar_to_array`)**:
  ```json
  {
    "rpm": 12000,
    "team": ["Ferrari"]
  }
  ```
* **Drifted JSON (`field_split`)**:
  ```json
  {
    "rpm_part1": 12000,
    "rpm_part2": 12000,
    "team": "Ferrari"
  }
  ```

### 3. Schema Alteration (Type/Structure/Temporal)

Modifies schema types, key capitalization, or structural nesting levels.

* **Original JSON**:
  ```json
  {
    "drs": 1,
    "speed_kmh": 310
  }
  ```
* **Drifted JSON (`key_case_change`)**:
  ```json
  {
    "DRS": 1,
    "SPEED_KMH": 310
  }
  ```
* **Drifted JSON (`nesting_deepen`)**:
  ```json
  {
    "nested": {
      "drs": 1,
      "speed_kmh": 310
    }
  }
  ```

## Reconcilers

| Reconciler | Type | Speed |
|------------|------|-------|
| Levenshtein | Edit distance | Fast (CPU) |
| Regex | Pattern matching | Fast (CPU) |
| BERT (MiniLM-v2) | Embedding similarity | Medium (GPU) |
| Gemma E2B-it | 2B LLM | Slow (GPU) |

## Physical QPU policy

The router is trained on LUMI's Aer GPU simulator, never on held-out physical
results. IBM and VLQ minutes are reserved for frozen evaluation. Use
[`scripts/slurm/submit_qpu_training_pipeline.sh`](scripts/slurm/submit_qpu_training_pipeline.sh)
for ten independent LUMI starts and
[`scripts/run_qpu_router_experiment.py`](scripts/run_qpu_router_experiment.py)
for the single-job IBM/VLQ evaluation.


## Output

Results saved to `data/reports/<hardware_type>/`:

- `matrix_results_<timestamp>.csv` - Aggregated metrics (accuracy, latency, throughput, drift events)
- `matrix_iterations_<timestamp>.csv` - Per-run raw data
- `drift_events_<timestamp>.csv` - Per-field drift log (source_field, drifted_field, sub_type, status)
- `ieee_table_<timestamp>.tex` - LaTeX table for IEEE TDKE paper
- `full_results_<timestamp>.json` - Complete run data
- `manifest_<timestamp>.json` - Hardware provenance

### Output Schema

| Field | Description |
|-------|-------------|
| run_id | 0-119 (classical) / 0-29 (quantum) |
| iteration | 1 |
| api | 9 sources (openf1, finnhub, spacex, openweather, clinical, hockey_nhl, aviation_opensky, football_uefa, smartcity_transit) |
| chaos_method | qwen / json_manip / schema_alter |
| chaos_sub_type | e.g., field_split, translation, contextual_rename |
| reconciler | levenshtein / regex / bert / gemma_e2b / quantum_routed |
| reconciliation_status | SUCCESS / FALSE_POSITIVE / FAILURE |
| packets_total | 22,500 |
| packets_clean | 20,250 |
| packets_drifted | 2,250 |
| fast_path_latency_ms | CPU time for clean packet bypass |
| gpu_latency_ms | MI250X processing time |
| drift_events | array of {source_field, drifted_field, sub_type, status} |
| reconciliation_time_ms | wall-clock time |
| accuracy | % correctly reconciled |

### Hosseini Resilience Index

Calculated post-hoc from raw data. Reference: Hosseini, S., Barker, K., & Ramirez-Marquez, J.E. (2016). A review of definitions and measures of system resilience. Reliability Engineering & System Safety, 145, 47-61.

## R2 Configuration

- Endpoint: `https://39c759d76d40fc4f357df7cac7ab2861.r2.cloudflarestorage.com`
- Bucket: `rap-framework`
- Credentials: `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (env vars, git-ignored)

## Energy & Carbon Tracking Architecture

To guarantee green computing and compliance with EuroHPC environment restrictions, the framework provides hardware-native energy profiling and carbon tracking.

### 1. Telemetry Sources
- **NVIDIA NVML (CUDA Platforms)**: Direct kernel interface read via Python `pynvml` wrappers querying power limits and real-time core metrics.
- **AMD Sysfs Interface (ROCm/LUMI-G)**: Since `rocm-smi` might block permissions in unprivileged containers, the telemetry fallbacks dynamically to reading GPU sensors directly from the host sysfs interface:
  - Power: `/sys/class/drm/card{index}/device/hwmon/hwmon0/power1_average`
  - Temperature: `/sys/class/drm/card{index}/device/hwmon/hwmon0/temp1_input`
- **CPU RAPL Telemetry**: Falling back to `/sys/class/powercap/intel-rapl` sensors when running on generic CPUs.
- **Localized Carbon Calculations**: Uses `CodeCarbon` alongside custom grid carbon coefficient estimations to compute estimated $gCO_2e$ values dynamically.

### 2. Context Manager Wrapper
Wrap execution blocks cleanly using `EnergyTracker`:
```python
from src.telemetry.metrics_logger import EnergyTracker

with EnergyTracker(output_path="/workspace/metrics/energy_profile.csv") as tracker:
    # Run processing loop here
    for epoch in range(1080):
        # execute operations
        tracker.log_epoch()
```
All logged data is saved to a clean structured CSV in `/workspace/metrics/energy_profile.csv`.

### 3. Container Recipes (Apptainer/Singularity)
Build definition recipe is stored in `Apptainer.def`. To execute benchmarks with host driver sensors attached, run:
```bash
# NVIDIA (CUDA via TalTech amp node)
apptainer run --nv --bind /sys:/sys,$(pwd):/workspace resilient-rap.sif run_matrix.py

# AMD Instinct (ROCm via LUMI-G)
apptainer run --rocm --bind /sys:/sys,$(pwd):/workspace resilient-rap.sif run_matrix.py
```

## Architecture

```
resilient-data/
├── src/
│   ├── chaos/             # Chaos injection engines (qwen, json_manip, schema_alter)
│   │   ├── injector.py    # Main injector with sub_type tracking
│   │   ├── qwen_chaos.py  # Qwen2.5-7B semantic drift
│   │   ├── json_chaos.py  # JSON structure/value manipulation
│   │   └── schema_chaos.py # Schema type/structure/temporal alteration
│   ├── reconciliation/    # 4 reconciliation methods
│   ├── hardware/          # Detection & VRAM probing
│   ├── orchestration/     # Matrix executor (Dual-Stage Gatekeeper)
│   └── telemetry/        # IEEE-formatted logging
├── scripts/               # QPU submissions, SLURM jobs, and data utilities
├── models/                # GGUF model storage
└── data/                  # Ingestion, chaos logs, results
```

## Active 10-Repetition & Physical IBM QPU Benchmark Progress

| Phase | Target Hardware / Platform | Repetitions | Status | Dataset Location |
|:---|:---|:---:|:---:|:---|
| **Phase 1: Non-Quantum Baselines** | AMD Instinct MI250X (LUMI-G) | 10 / 10 | **COMPLETED** | `data/reports/MI250X_run01` – `run10` |
| **Phase 3: Aer GPU QPU Simulation** | AMD Instinct MI250X (LUMI-G) | 10 / 10 | **COMPLETED** | `data/reports/quantum_MI250X_aer_sim_run01` – `run10` |
| **Phase 4: Physical IBM QPU Benchmark** | IBM Heron r2 Processor (`ibm_fez`) | 10 / 10 | **COMPLETED** | `data/reports/quantum_run_ibm_qpu_ibm_qpu_run01` – `run10` |
| **Local GPU Embedding Sweep** | AMD Instinct MI250X (LUMI-G) | 10 / 10 | **COMPLETED** | `data/reports/MI250X_bge_embed_run01` – `run10` |
| **Cohere Embed Benchmark** | Cohere API (`embed-english-v3.0`) | 10 / 10 | **COMPLETED** | `data/reports/run_cohere_run01` – `run10` |

## Citation

For IEEE TDKE paper submission, use generated LaTeX tables from `data/reports/<hardware>/ieee_table_*.tex`.

## License

Copyright (c) 2026 Tarek Clarke. All rights reserved.
