# Resilient RAP Framework

**Resilient API Adaptation Protocol** - End-to-end chaos engineering and reconciliation framework for telemetry data streams.

## Overview

Executes a 100-combination matrix: **10 APIs × 3 Chaos Methods × 4 Reconcilers × 1 Iteration** across heterogeneous hardware platforms.

### Components

- **Ingestion**: Seeding and synthetically generating telemetry for 10 domains (OpenF1, Finnhub, SpaceX, OpenMeteo, FDA Clinical, NHL Hockey Event Streams, OpenSky Aviation Vectors, UEFA Football Match Events, SensorCommunity IoT, TfL Transit Predictions).
- **Chaos Engineering**: 10% injection rate via Qwen2.5-7B (semantic synonyms), JSON manipulation (structure/value changes), schema alteration (type/nesting depth).
- **Reconciliation**: Levenshtein, Regex, BERT (MiniLM-v2), Gemma E4B-it.
- **Hardware Detection**: Auto-bootstrap for CUDA, ROCm, Apple Silicon, CPU with VRAM probing.
- **Energy & Carbon Profiling**: Integrated `EnergyTracker` wrapping execution blocks for real-time power, temp, and carbon intensity measurement (using CodeCarbon + native NVML/Sysfs wrappers for NVIDIA and AMD Instinct GPUs).

### Target Volume

- **25,000 packets** total (2,500 per API source across all 10 domains)
- **2,500 chaos injections** (10% of total)
- **22,500 clean packets** (fast-path bypass, no GPU)


## Hardware Matrix

| Supercomputer / Platform | Processor Tier | Accelerator / Backend | VRAM | Concurrent Runs | Batch Size |
|:---|:---|:---|:---|:---|:---|
| **LUMI-G (EuroHPC)** | AMD EPYC | AMD Instinct MI250X (ROCm) | 128 GB | 12 | 32 |
| **Jupiter (EuroHPC)** | NVIDIA Grace | NVIDIA GH200 (CUDA) | 96 GB | 12 | 32 |
| **MareNostrum 5 (EuroHPC)** | Intel Xeon / AMD EPYC | CUDA H100 / ROCm MI300 | 80 GB / 192 GB | 8 / 16 | 32 |
| **Apple Macbook Pro** | Apple M4 Max | Metal Performance Shaders (MPS) | 48 GB | 3 | 16 |
| **Local CPU Sandbox** | Generic x86_64 | CPU Fallback (RealAmplitudes) | N/A | 1 | 4 |


## Quick Start

```bash
# 1. Clone
git clone https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
git checkout domain_testing

# 2. Detect hardware
./deploy/detect_hardware.sh

# 3. Download models from R2
chmod +x models/download_from_r2.sh && ./models/download_from_r2.sh

# 4. Ingest 10k packets (cloud instance)
cd go/ingestion && go run main.go

# 5. Upload to R2 (Mac)
python scripts/upload_to_r2.py

# 6. Bootstrap and run matrix (cloud instance)
python run_matrix.py
```

## Benchmark Configuration

### Run Matrix (48 Runs)

- 4 APIs × 3 chaos methods × 4 reconcilers × 1 iteration = 48 total runs
- 48 unique combinations

### Per-Run Data (10,000 Packets)

| Metric | Value |
|--------|-------|
| Total packets | 10,000 (2,500 per API) |
| Clean (fast-path bypass) | 9,000 (90%) |
| Drifted (GPU reconciliation) | 1,000 (10%) |
| GPU batches per reconciler | 16 (batch_size=64) |

## 10-Repetition Systems & QPU Benchmark Results (Placeholders)

The following tables show the results of the 10-repetition sweeps comparing the classical reconciler tiers, the GPU-accelerated Quantum VQC Simulator, and the physical Star VLQ 24-Qubit QPU backend across all 10 API sources. 

### Global Performance, Energy, and Carbon savings Summary
| Routing Strategy | Mean Accuracy (%) | Avg Latency (ms) | Energy / Packet (J) | Carbon / Packet (mg CO2e) | Carbon Saved vs. Gemma Baseline (%) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Classical LLM (Gemma)** | *[Gemma Accuracy]* | *[Gemma Latency]* | *[Gemma Energy]* | *[Gemma Carbon]* | *[0.0%]* |
| **Quantum Router (Sim)**  | *[Sim Accuracy]*   | *[Sim Latency]*   | *[Sim Energy]*   | *[Sim Carbon]*   | *[Sim Savings]* |
| **Quantum Router (QPU)**  | *[QPU Accuracy]*   | *[QPU Latency]*   | *[QPU Energy]*   | *[QPU Carbon]*   | *[QPU Savings]* |

### API-Specific Performance Tables

#### 1. OpenF1 Telemetry
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 2. Finnhub Financial Feeds
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 3. SpaceX Telemetry
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 4. OpenWeather Vectors
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 5. FDA Clinical Records
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 6. NHL Hockey Event Streams
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 7. OpenSky Aviation Vectors
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 8. UEFA Football Match Events
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 9. SensorCommunity IoT
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

#### 10. TfL Transit Predictions
| Reconciler / Router | Mean Accuracy (%) | Avg Latency (ms) | Energy (J) | Carbon Offset (mg) |
|:---|:---:|:---:|:---:|:---:|
| Levenshtein | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Regex | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| BERT | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| Gemma-4B | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (Sim)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |
| **Quantum Router (QPU)** | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |


## Live F1 Telemetry Decoder (LUMI Deployment)

This pipeline runs a real-time, GPU-accelerated schema reconciliation loop on live F1 telemetry data from OpenF1 on LUMI. 

Because LUMI compute nodes do not have external internet access, the pipeline uses a **dual-node architecture**:
1. **Go Ingestor** (runs on a login/interactive node): Streams live telemetry from `api.openf1.org` and writes to the shared Lustre directory.
2. **GPU Decoder** (runs on a compute node under SLURM): Polls the ingested telemetry, injects schema/JSON drift, and runs the BERT/reconciler model on the AMD MI250X GPU in batches.

### Step-by-Step Instructions

#### 1. Start the Ingestor (Terminal 1 - Login Node)
Navigate to the Go ingestion directory and execute the ingestor. This will download and write packets to `data/ingested/telemetry_latest.json`.
```bash
cd go/ingestion
go run .
```
*Note: This runs in the background asynchronously writing and flushing packets atomically to prevent blocking I/O starvation.*

#### 2. Start the Decoder (Terminal 2 - Compute Node via SLURM)
From the project root directory, submit the SLURM job to allocate a `dev-g` node with an AMD MI250X GPU:
```bash
sbatch submit_live_decoder.slurm
```

To watch the live decoding statistics (warmup, throughput, accuracy, and average latency per packet), run:
```bash
tail -f live_decoder_<JOB_ID>.out
```

#### 3. Stopping the Pipeline
* **Ingestor**: Press `Ctrl+C` in your Go terminal to gracefully terminate and write the final file.
* **Decoder**: Cancel the SLURM job using `scancel <JOB_ID>`.
* **Reports**: Results, including a metrics CSV and a JSON provenance manifest, are automatically written to `data/reports/live_f1/`.

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

## Running Quantum Benchmarks on LUMI

Follow these instructions to run the quantum simulation sweeps, router ablation comparisons, and training grid search benchmarks using the AMD MI250X GPU environment on LUMI.

### 1. Clone and Setup Environment
Load the required LUMI modules and activate your virtual environment:
```bash
# Clone the repository (quantum branch)
cd /scratch/project_465002996/clarketa
git clone -b quantum https://github.com/tarek-clarke/resilient-rap-framework.git resilient-rap-quantum
cd resilient-rap-quantum

# Load environment modules
module load LUMI/25.09
module load partition/G
module load rocm/6.3.4
module load cray-python/3.10.10

# Activate Python virtual environment
source .venv-lumi/bin/activate
```

### 2. Run Qiskit GPU Simulator Scaling Sweep
Run the benchmark script that measures simulation time scaling as a function of qubits and circuit depth on the AMD MI250X GPU via `AerSimulator`:
```bash
python3 run_scaling_sweep.py
```
*Outputs JSON metrics to `data/reports/quantum_gpu_scaling_sweep.json`.*

### 3. Run Router Ablation Study
Compare brute-force BERT (GPU only) vs. the hybrid quantum-routed (VQC + CPU fallbacks) pipeline performance:
```bash
# Run brute-force BERT baseline
python3 run_matrix.py --max-packets-per-api 500 --chaos-rate 0.05 --phases bert --suffix _bert_only

# Run quantum-routed pipeline (using Aer GPU simulator)
python3 run_matrix.py --max-packets-per-api 500 --chaos-rate 0.05 --phases quantum --backend aer_simulator --suffix _quantum_routed
```

### 4. Run VQC Training Grid Search
Evaluate routing model parameter fitting convergence across various optimizers (COBYLA, SPSA) and feature maps:
```bash
python3 run_training_sweep.py
```
*Outputs grid search metrics to `data/reports/router_training_grid_search.json`.*

*(Note: Gemma-7B/4B local semantic reconciliation benchmarking has been omitted from the grid configurations as it is extremely compute-heavy).*


## Dual-Stage Gatekeeper Architecture

### Stage 1: Fast-Path Bypass (CPU)
- Every packet in the stream executes a deterministic structural check
- Matching packet keys against the target expected schema template
- If the packet is 100% clean: instantly append to in-memory execution log and short-circuit to next packet
- **No GPU reconciler calls for clean packets**

### Stage 2: GPU Routing (B300)
- Only packets that fail the schema verification check (anomalies/drift) are routed to GPU
- Batch size: 64 (dynamically adjusted to VRAM)
- Deferred bulk I/O: all results accumulated in RAM and serialized in single write after matrix run

### Per-Run Processing
```
For each of 48 runs:
  for each packet in 10,000:
    if packet is clean (schema check passes):
      → append to in-memory log → continue (bypass GPU)
    else:
      → route to GPU batch queue (batch_size=64)
  after all packets:
    → GPU processes 16 batches × 4 reconcilers
    → bulk write all results to disk in one I/O block
```

### Estimated Runtime (B300, 1 GPU)

| Metric | Value |
|--------|-------|
| Per run | ~5 sec |
| 48 runs | ~4-5 min |
| Well under 1-hour budget | ✓ |

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
| Gemma E4B-it | 4B LLM | Slow (GPU) |

## Heterogeneous Supercomputer Docker Build & Run

A single unified Docker container serves all EuroHPC environments. The entrypoint script dynamically detects hardware capabilities (CUDA/ROCm/CPU) and binds runtime configurations.

### 1. Build Container Image

```bash
docker build -t resilient-rap-framework:latest .
```

### 2. Runtime Execution & Bootstrapping

To run the full benchmark on local environments or inside supercomputer partitions, mount the workspace and optionally pass API keys:

```bash
# General Docker Execution with GPU access (CUDA / NVIDIA)
docker run --gpus all \
  -e IBM_QUANTUM_API_TOKEN="YOUR_API_KEY" \
  -v $(pwd)/data:/workspace/data \
  -v $(pwd)/metrics:/workspace/metrics \
  resilient-rap-framework:latest

# AMD ROCm / LUMI-G Interactive Docker (using ROCm DRI device access)
docker run --device=/dev/kfd --device=/dev/dri \
  -e IBM_QUANTUM_API_TOKEN="YOUR_API_KEY" \
  -v $(pwd)/data:/workspace/data \
  -v $(pwd)/metrics:/workspace/metrics \
  resilient-rap-framework:latest
```

### 3. IBM Quantum training on QPU instance

To trigger the `RoutingTrainer` using the physical IBM QPU hardware (e.g. `ibm_quantum` backend) rather than the local simulator, invoke:

```bash
python3 run_matrix.py --phases quantum --backend ibm_quantum
```


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
| run_id | 0-47 |
| iteration | 1 |
| api | spacex / openf1 / iexcloud / openmeteo |
| chaos_method | qwen / json_manip / schema_alter |
| chaos_sub_type | e.g., field_split, translation, contextual_rename |
| reconciler | levenshtein / regex / bert / gemma_e4b |
| reconciliation_status | SUCCESS / FALSE_POSITIVE / FAILURE |
| packets_total | 10,000 |
| packets_clean | 9,000 |
| packets_drifted | 1,000 |
| fast_path_latency_ms | CPU time for clean packet bypass |
| gpu_latency_ms | B300 processing time |
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

## Batch Size Scaling


| VRAM | Batch Size | Target Hardware |
|------|------------|-----------------|
| < 16 GB | 4 | CPU, M4 |
| 16-31 GB | 8 | 7900XT, M4 Pro |
| 32-79 GB | 16 | RTX 5090, RTX 6000 |
| 80-199 GB | 32 | A100, H100, GH200, MI250X |
| ≥ 200 GB | 64 | B300 |

## Architecture

```
resilient-data/
├── go/ingestion/          # Go async streaming clients
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
├── scripts/               # upload_to_r2.py, mock_stream.py
├── models/                # GGUF model storage
├── deploy/                # Docker, Slurm, native scripts
├── configs/               # API endpoints, hardware profiles
└── data/                  # Ingestion, chaos logs, results
```

## Citation

For IEEE TDKE paper submission, use generated LaTeX tables from `data/reports/<hardware>/ieee_table_*.tex`.

## License

Copyright (c) 2026 Tarek Clarke. All rights reserved.