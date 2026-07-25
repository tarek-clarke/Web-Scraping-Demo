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

The active workflow and evaluation pipeline for the paper are driven by the following core scripts:

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

The following tables summarize the completed 10-repetition multi-GPU (AMD Instinct MI250X) and physical IBM Quantum QPU sweeps over the 9-API benchmark corpus. Exactly 27 out of 27 physical QPU batch jobs (`d9hr0dogk0ls73f3ehi0` through `d9hra54honhs73adh62g`) executed live on the 156-qubit IBM Eagle QPU (`ibm_fez`) via `SamplerV2`. All raw datasets and LaTeX tables are versioned in [data/reports/quantum_run_ibm_qpuibm_qpu_mac_run/](file:///Users/tarekclarke/resilient-rap-framework/data/reports/quantum_run_ibm_qpuibm_qpu_mac_run/) and synced with `origin/tkde`.

### Global Performance Summary Across All 9 APIs (Combined)
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 75.57% | 0.392ms | 0.000J | 0.00mg |
| Regex | 80.15% | 0.637ms | 0.000J | 0.00mg |
| BERT | 88.63% | 35.596ms | 0.001J | 105.70mg |
| BGE Local GPU Embedding (LUMI-G) | 87.70% | 37.766ms | 0.001J | 108.60mg |
| Cohere Embed (embed-english-v3.0) | 74.35% | 455.943ms | 0.005J | 660.80mg |
| Gemma 4 E2B (4-bit) | 41.89% | 3938.093ms | 0.080J | 11421.21mg |
| Quantum Router (Sim - MI250X Aer GPU) | 92.78% | 3.327ms | 9.290J | 11490.87mg |
| Quantum Router (IBM QPU - ibm_fez) | **38.93%** | **0.0180ms** | **9.290J** | **11490.87mg** |
| Quantum Router (VLQ QPU) | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

### Global Strategy Comparison Summary
| Routing Strategy | Mean Accuracy (%) | Avg Latency (ms) | Energy / Packet (J) | Carbon / Packet (mg CO2e) | Carbon Saved vs. Gemma Baseline (%) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Classical LLM (Gemma 4 E2B 4-bit)** | 44.20% | 4593.70ms | 0.093J | 63.53mg | 0.0% |
| **Quantum Router (Sim - MI250X Aer GPU)**  | 92.00% | 3.05ms | 9.29J | 14.86mg | 76.61% |
| **Quantum Router (IBM QPU - ibm_fez)** | **38.69%** | **0.0156ms** | 9.29J | 14.86mg | 76.61% |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

> **IBM QPU Hardware Execution Summary**: All 27 physical `SamplerV2` circuit payload batches were submitted directly to `ibm_fez` (156-qubit Eagle physical QPU). Quantum hardware execution time per batch ranged between **4 seconds and 8 seconds**, achieving an ultra-low mean evaluation latency of **0.0156 ms** per packet.

> [!NOTE]
> **Energy Metrics Interpretation**: Classical reconcilers (Levenshtein and Regex) execute strictly on CPU threads using parallel processes. Because the integrated hardware profiling tools measure active GPU-specific accelerator energy consumption (e.g. Instinct MI250X GCD power state probing), these CPU-bound tasks are reported as `0.000J` in the GPU-focused energy comparison matrix.

### API-Specific Performance Tables

#### 1. OpenF1 Telemetry
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 83.52% | 0.228ms | 0.000J | 0.00mg |
| Regex | 78.87% | 0.419ms | 0.000J | 0.00mg |
| BERT | 93.79% | 75.437ms | 0.002J | 240.23mg |
| BGE Local GPU (LUMI-G) | 93.50% | 9.718ms | 0.001J | 28.10mg |
| Cohere Embed (embed-english-v3.0) | 83.94% | 437.518ms | 0.005J | 634.10mg |
| Gemma 4 E2B (4-bit) | 42.10% | 3855.591ms | 0.078J | 11050.40mg |
| **Quantum Router (Sim)** | 96.80% | 25.93ms | 9.29J | 10834.12mg |
| **Quantum Router (IBM QPU - ibm_fez)** | **45.81%** | **0.0137ms** | 9.29J | 10834.12mg |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 2. Finnhub Financial Feeds
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 71.50% | 0.062ms | 0.000J | 0.00mg |
| Regex | 83.88% | 0.068ms | 0.000J | 0.00mg |
| BERT | 83.22% | 76.295ms | 0.002J | 243.11mg |
| BGE Local GPU (LUMI-G) | 81.75% | 10.120ms | 0.001J | 29.30mg |
| Cohere Embed (embed-english-v3.0) | 71.62% | 534.078ms | 0.006J | 774.20mg |
| Gemma 4 E2B (4-bit) | 60.97% | 3871.199ms | 0.079J | 11124.50mg |
| **Quantum Router (Sim)** | 87.55% | 0.46ms | 9.29J | 10986.20mg |
| **Quantum Router (IBM QPU - ibm_fez)** | **40.89%** | **0.0044ms** | 9.29J | 10986.20mg |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 3. SpaceX Telemetry
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 67.01% | 0.083ms | 0.000J | 0.00mg |
| Regex | 76.28% | 0.326ms | 0.000J | 0.00mg |
| BERT | 87.69% | 2.332ms | 0.000J | 8.21mg |
| BGE Local GPU (LUMI-G) | 88.40% | 4.459ms | 0.000J | 12.90mg |
| Cohere Embed (embed-english-v3.0) | 74.68% | 374.031ms | 0.004J | 542.10mg |
| Gemma 4 E2B (4-bit) | 40.09% | 2442.795ms | 0.050J | 7015.42mg |
| **Quantum Router (Sim)** | 95.00% | 0.47ms | 9.29J | 6831.25mg |
| **Quantum Router (IBM QPU - ibm_fez)** | **42.00%** | **0.0049ms** | 9.29J | 6831.25mg |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 4. OpenWeather Vectors
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 68.80% | 0.019ms | 0.000J | 0.00mg |
| Regex | 85.42% | 0.222ms | 0.000J | 0.00mg |
| BERT | 86.69% | 11.304ms | 0.000J | 36.17mg |
| BGE Local GPU (LUMI-G) | 85.36% | 19.025ms | 0.001J | 55.10mg |
| Cohere Embed (embed-english-v3.0) | 70.87% | 391.680ms | 0.004J | 567.80mg |
| Gemma 4 E2B (4-bit) | 50.50% | 3464.710ms | 0.071J | 9951.25mg |
| **Quantum Router (Sim)** | 91.51% | 0.46ms | 9.29J | 9741.05mg |
| **Quantum Router (IBM QPU - ibm_fez)** | **32.20%** | **0.0058ms** | 9.29J | 9741.05mg |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 5. FDA Clinical Records
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 74.41% | 0.052ms | 0.000J | 0.00mg |
| Regex | 73.01% | 0.163ms | 0.000J | 0.00mg |
| BERT | 91.12% | 100.062ms | 0.003J | 321.44mg |
| BGE Local GPU (LUMI-G) | 88.86% | 173.810ms | 0.005J | 503.20mg |
| Cohere Embed (embed-english-v3.0) | 74.56% | 391.066ms | 0.004J | 566.90mg |
| Gemma 4 E2B (4-bit) | 67.05% | 3735.446ms | 0.076J | 10735.10mg |
| **Quantum Router (Sim)** | 96.34% | 0.48ms | 9.29J | 10413.20mg |
| **Quantum Router (IBM QPU - ibm_fez)** | **37.85%** | **0.0084ms** | 9.29J | 10413.20mg |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 6. NHL Hockey Event Streams
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 91.09% | 2.018ms | 0.000J | 0.00mg |
| Regex | 81.84% | 2.978ms | 0.000J | 0.00mg |
| BERT | 97.95% | 22.319ms | 0.000J | 73.11mg |
| BGE Local GPU (LUMI-G) | 98.30% | 43.658ms | 0.001J | 126.50mg |
| Cohere Embed (embed-english-v3.0) | 82.29% | 606.503ms | 0.007J | 879.30mg |
| Gemma 4 E2B (4-bit) | 3.85% | 5524.083ms | 0.113J | 15865.10mg |
| **Quantum Router (Sim)** | 98.74% | 0.60ms | 9.29J | 15582.40mg |
| **Quantum Router (IBM QPU - ibm_fez)** | **34.87%** | **0.0561ms** | 9.29J | 15582.40mg |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 7. OpenSky Aviation Vectors
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 48.92% | 0.012ms | 0.000J | 0.00mg |
| Regex | 73.68% | 0.277ms | 0.000J | 0.00mg |
| BERT | 65.28% | 22.816ms | 0.000J | 72.82mg |
| BGE Local GPU (LUMI-G) | 61.09% | 53.552ms | 0.002J | 155.20mg |
| Cohere Embed (embed-english-v3.0) | 43.63% | 350.798ms | 0.004J | 508.60mg |
| Gemma 4 E2B (4-bit) | 71.92% | 1492.944ms | 0.031J | 4287.31mg |
| **Quantum Router (Sim)** | 73.99% | 0.46ms | 9.29J | 4081.22mg |
| **Quantum Router (IBM QPU - ibm_fez)** | **23.65%** | **0.0031ms** | 9.29J | 4081.22mg |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 8. UEFA Football Match Events
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 84.18% | 0.299ms | 0.000J | 0.00mg |
| Regex | 81.04% | 0.638ms | 0.000J | 0.00mg |
| BERT | 94.99% | 7.754ms | 0.000J | 24.81mg |
| BGE Local GPU (LUMI-G) | 95.22% | 21.992ms | 0.001J | 63.70mg |
| Cohere Embed (embed-english-v3.0) | 83.92% | 483.010ms | 0.005J | 700.30mg |
| Gemma 4 E2B (4-bit) | 25.21% | 2818.666ms | 0.058J | 8092.12mg |
| **Quantum Router (Sim)** | 97.02% | 0.51ms | 9.29J | 7942.33mg |
| **Quantum Router (IBM QPU - ibm_fez)** | **39.52%** | **0.0185ms** | 9.29J | 7942.33mg |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 9. TfL Transit Predictions
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | 91.70% | 0.755ms | 0.000J | 0.00mg |
| Regex | 87.31% | 0.643ms | 0.000J | 0.00mg |
| BERT | 96.96% | 2.042ms | 0.000J | 6.53mg |
| BGE Local GPU (LUMI-G) | 96.81% | 3.557ms | 0.000J | 10.30mg |
| Cohere Embed (embed-english-v3.0) | 83.57% | 493.391ms | 0.005J | 715.40mg |
| Gemma 4 E2B (4-bit) | 15.28% | 8237.395ms | 0.169J | 23649.80mg |
| **Quantum Router (Sim)** | 98.03% | 0.57ms | 9.29J | 23512.44mg |
| **Quantum Router (IBM QPU - ibm_fez)** | **53.56%** | **0.0471ms** | 9.29J | 23512.44mg |
| **Quantum Router (VLQ QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |




---

## Quantum-Accelerated Routing Architecture

To optimize data streams dynamically on heterogeneous hardware, the framework incorporates a **Quantum Routing Module** utilizing a **Variational Quantum Classifier (VQC)** to route drifted telemetry packets to the optimal classical or semantic reconciler (Levenshtein, Regex, or BERT).

### 1. Feature Extraction & Scaling
For each original/drifted packet pair, the `FeatureExtractor` extracts 10 structural and semantic properties:
1. `field_count` - Normalized total fields in expected schema (max 50)
2. `nesting_depth` - Maximum nesting depth of JSON structure (max 5)
3. `numeric_ratio` - Percentage of values that are float/int
4. `string_ratio` - Percentage of values that are string
5. `fields_added` - Count of newly introduced fields normalized by field_count
6. `fields_removed` - Count of removed fields normalized by field_count
7. `key_edit_distance_mean` - Mean Levenshtein distance between expected and drifted keys (max 10)
8. `has_type_changes` - Binary (0 or 1) indicating if key values changed types
9. `has_structural_changes` - Binary (0 or 1) indicating if JSON structural layers changed
10. `source_encoded` - Ordinal value encoding API source (openf1=0.25, finnhub=0.5, spacex=0.75, openweather=1.0)

All features are normalized to `[0, 1]` and then scaled to `[0, \pi]` for quantum angle encoding.

### 2. Variational Quantum Circuit (VQC) Design
The classification circuit is built using Qiskit:
* **Feature Mapping**: A `ZZFeatureMap` (2 repetitions) encodes the 10-dimensional scaled feature vector into 10 qubits using angle-encoding gates.
* **Variational Ansatz**: A `RealAmplitudes` circuit (2 output qubits added, 12 qubits total, 2 repetitions) entangles the feature space and output space using trainable $R_y$ rotation gates and CNOT entangling gates.
* **Measurement**: The 2 output qubits are measured to yield a 2-bit class string (`00`=Levenshtein, `01`=Regex, `10`=BERT, `11`=Gemma).
* **Execution**: Circuits are transpiled and run on the local `AerSimulator` or via IBM Quantum Runtime services.

### 3. Training & Alignment
The `RoutingTrainer` module scans historical baseline benchmark runs from `data/reports/` to construct training matrices:
- For each unique (API, Chaos Method, Chaos Sub-Type) combination, it isolates which reconciler yielded the highest reconciliation accuracy. If accuracy ties, it selects the reconciler with the lowest latency.
- These labels are mapped into one-hot integers and fit using a COBYLA optimizer (200 iterations max).
- If no trained model weights exist, the VQC defaults gracefully to zero-weight binding and classical fallback trees derived from hardware performance baselines.

### 4. Empirical Systems Telemetry & Ecological Audit
To validate the efficiency of the quantum routing layer for top-tier systems venues, the framework collects detailed operational metrics:
* **Quantum Hardware execution**: Logs the physical `qpu_execution_time_ms`, gate fidelity, and coherence status vs. classical simulation time.
* **Routing Decision Confusion Matrix**: Evaluates the routing decision against the theoretical `optimal_reconciler` (the lowest-compute reconciler that achieves $\ge 95\%$ accuracy). It tabulates False Positives (routing cheap drifts to LLMs) and False Negatives (routing semantic drifts to Levenshtein, failing SLA).
* **Ecological Power Savings**: Dynamically tracks active GPU and CPU energy (in Joules). It computes the `estimated_carbon_offset_mg` comparing actual energy draw against the baseline where all drifted packets are routed to the heavy Gemma fallback.

### Current Accuracy Diagnosis
The present IBM hardware run should be treated as diagnostic rather than final paper-quality evidence. The current result is dominated by two mismatches: the deployed inference circuit is not identical to the training circuit, and the training labels are derived from a coarser aggregate oracle than the packet-level evaluation used in the benchmark.

Observed run-31 metrics:

- packet-level routing decision match: `45.79%`
- balanced accuracy: `33.58%`
- macro-F1: `33.32%`
- always-Levenshtein baseline: `51.14%`
- always-BERT baseline: `45.75%`

The paper-ready write-up lives in [`docs/QUANTUM_ROUTING_ACCURACY_DIAGNOSIS.md`](docs/QUANTUM_ROUTING_ACCURACY_DIAGNOSIS.md).

## Current Workflow

The maintained end-to-end commands for this branch live in
[`docs/QPU_SINGLE_JOB_WORKFLOW.md`](docs/QPU_SINGLE_JOB_WORKFLOW.md). That runbook covers the current LUMI training path plus the one-job IBM and VLQ physical-QPU submission flow.

### Step 3 — Submit Shadow Logs to Physical QPU

Once a shadow run log (`shadow_log_*.json`) is isolated, submit it to IBM Quantum for physical execution replay:

```bash
# Set your IBM Quantum API key
export QISKIT_IBM_TOKEN="your_ibm_token_here"

# Submit shadow log to physical QPU
python3 scripts/submit_shadow_qpu.py \
  --log data/reports/completed_shadow_runs/run_1/shadow_log_<timestamp>.json \
  --backend ibm_quantum \
  --shots 1024
```

The script will:
1. Load the shadow log (packet features + emulator decisions)
2. Compile and transpile circuits for the IBM QPU
3. Execute the batch on physical quantum hardware
4. Compare QPU decisions vs. emulator decisions and save a `qpu_replay_report_*.json`

### Active Benchmark Parameters (IBM Quantum)

The currently executing physical QPU benchmark uses the following properties:
* **Job ID**: `d9dd55sjeosc73fhd94g`
* **Selected Least-Busy Backend**: `ibm_fez` (156 Qubits)
* **Total Packets Routed**: 5,200 circuits
* **Shots per Circuit**: 1,024
* **Ansatz Config**: `ZZFeatureMap` (2 reps) + `RealAmplitudes` (2 reps) on 12 qubits

Results are saved automatically to the specified output reports directory:

```json
{
  "backend": "ibm_quantum",
  "total_packets": 2500,
  "agreement_rate": 91.2,
  "results": [...]
}
```




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
| **Phase 4: Physical IBM QPU Benchmark** | IBM Eagle Processor (`ibm_fez`) | 10 / 10 | **COMPLETED** | `data/reports/quantum_run_ibm_qpu_ibm_qpu_run01` – `run10` |
| **Local GPU Embedding Sweep** | AMD Instinct MI250X (LUMI-G) | 10 / 10 | **COMPLETED** | `data/reports/MI250X_bge_embed_run01` – `run10` |
| **Cohere Embed Benchmark** | Cohere API (`embed-english-v3.0`) | 10 / 10 | **COMPLETED** | `data/reports/run_cohere_run01` – `run10` |

## Citation

For IEEE TDKE paper submission, use generated LaTeX tables from `data/reports/<hardware>/ieee_table_*.tex`.

## License

Copyright (c) 2026 Tarek Clarke. All rights reserved.
