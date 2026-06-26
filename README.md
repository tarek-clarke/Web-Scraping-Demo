# Resilient RAP Framework

**Resilient API Adaptation Protocol** - End-to-end chaos engineering and reconciliation framework for telemetry data streams.

## Overview

Executes 48-combination matrix: **4 APIs × 3 Chaos Methods × 4 Reconcilers × 1 Iteration** across heterogeneous hardware platforms.

### Components

- **Ingestion**: Go-based async streaming from 4 live APIs (OpenF1, IEX Cloud, SpaceX, OpenMeteo)
- **Chaos Engineering**: 10% injection rate via Qwen2.5-7B (semantic), JSON manipulation, schema alteration
- **Reconciliation**: Levenshtein, Regex, BERT (MiniLM-v2), Gemma E4B-it
- **Hardware Detection**: Auto-bootstrap for CUDA, ROCm, Apple Silicon, CPU with VRAM probing

### Target Volume

- **10,000 packets** total (2,500 per API source)
- **1,000 chaos injections** (10% of total)
- **9,000 clean packets** (fast-path bypass, no GPU)

## Hardware Matrix

| Platform | Type | VRAM | Concurrent Runs | Batch Size |
|----------|------|------|-----------------|------------|
| NVIDIA B300 | CUDA | 268 GB | 33 | 64 |
| NVIDIA RTX 6000 Blackwell | CUDA | 96 GB | 12 | 32 |
| NVIDIA RTX 5090 | CUDA | 32 GB | 3 | 16 |
| AMD MI250X | ROCm | 128 GB | 12 | 32 |
| Apple M4 | Silicon | 16 GB | 3 | 8 |

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

## AMD MI250X Benchmark Results

The following are the true mapping results obtained on a LUMI compute node with 1 AMD MI250X GPU (isolated as `cuda:0` for Gemma and `cuda:1` for Qwen chaos). This run properly deep-copied packets to test all chaos methods (Qwen, JSON manipulation, and schema alteration) without in-place mutation interference.

### True Mapping Throughput and Latency (Excluding Chaos Generation)

| Phase | API | Chaos Method | Reconciler | Accuracy | GPU Latency (ms) | GPU Throughput (pps) |
|:---|:---|:---|:---|---:|---:|---:|
| fast | openf1 | schema_alter | levenshtein | 47.4% | 0.8 | 4839.2 |
| fast | openf1 | json_manip | levenshtein | 94.6% | 92.6 | 161.9 |
| fast | openf1 | json_manip | regex | 82.6% | 3.3 | 4487.7 |
| fast | openf1 | schema_alter | regex | 81.1% | 0.9 | 4674.6 |
| fast | finnhub | json_manip | levenshtein | 96.2% | 14.3 | 1259.2 |
| fast | finnhub | json_manip | regex | 82.6% | 19.1 | 943.6 |
| fast | finnhub | schema_alter | levenshtein | 88.9% | 12.5 | 797.6 |
| fast | finnhub | schema_alter | regex | 83.2% | 2.0 | 4914.5 |
| fast | openf1 | qwen | regex | 81.8% | 5.3 | 4743.4 |
| fast | spacex | json_manip | levenshtein | 98.0% | 9.2 | 2496.0 |
| fast | spacex | json_manip | regex | 82.9% | 6.9 | 3337.2 |
| fast | spacex | schema_alter | levenshtein | 80.0% | 2.0 | 2444.8 |
| fast | spacex | schema_alter | regex | 82.9% | 1.5 | 3257.5 |
| fast | spacex | qwen | regex | 82.6% | 8.3 | 3001.1 |
| fast | openf1 | qwen | levenshtein | 91.9% | 5.3 | 4695.2 |
| fast | openweather | json_manip | levenshtein | 97.8% | 6.1 | 3296.5 |
| fast | openweather | json_manip | regex | 84.8% | 5.1 | 3897.3 |
| fast | openweather | schema_alter | levenshtein | 67.9% | 3.0 | 3284.4 |
| fast | openweather | schema_alter | regex | 83.0% | 2.6 | 3820.4 |
| fast | finnhub | qwen | levenshtein | 92.6% | 5.3 | 4716.9 |
| fast | finnhub | qwen | regex | 75.1% | 5.0 | 4985.0 |
| fast | spacex | qwen | levenshtein | 96.4% | 11.9 | 2095.9 |
| fast | openweather | qwen | levenshtein | 97.5% | 8.2 | 3036.2 |
| fast | openweather | qwen | regex | 85.0% | 6.4 | 3923.9 |
| bert | openf1 | json_manip | bert | 96.8% | 1207.7 | 13.2 |
| bert | openf1 | schema_alter | bert | 98.5% | 1229.9 | 5.7 |
| bert | finnhub | json_manip | bert | 97.3% | 1254.8 | 15.9 |
| bert | finnhub | schema_alter | bert | 95.9% | 1287.0 | 7.0 |
| bert | spacex | json_manip | bert | 99.6% | 81.4 | 307.1 |
| bert | spacex | schema_alter | bert | 98.0% | 68.9 | 101.6 |
| bert | openweather | json_manip | bert | 98.2% | 44.3 | 429.3 |
| bert | openweather | schema_alter | bert | 97.9% | 22.9 | 523.8 |
| bert | openf1 | qwen | bert | 98.6% | 18.2 | 1373.1 |
| bert | finnhub | qwen | bert | 82.2% | 18.4 | 1358.2 |
| bert | spacex | qwen | bert | 98.2% | 17.9 | 1398.9 |
| bert | openweather | qwen | bert | 99.1% | 12.5 | 1999.3 |
| gemma | openf1 | qwen | gemma_e4b | 8.8% | 86855.1 | 0.3 |
| gemma | openf1 | json_manip | gemma_e4b | 27.9% | 69405.5 | 0.2 |
| gemma | openf1 | schema_alter | gemma_e4b | 49.1% | 91254.5 | 0.1 |
| gemma | finnhub | qwen | gemma_e4b | 84.8% | 307641.7 | 0.1 |
| gemma | finnhub | json_manip | gemma_e4b | 22.4% | 138618.6 | 0.1 |
| gemma | finnhub | schema_alter | gemma_e4b | 39.2% | 85249.1 | 0.1 |
| gemma | spacex | qwen | gemma_e4b | 5.9% | 111786.1 | 0.2 |
| gemma | spacex | json_manip | gemma_e4b | 6.8% | 80755.4 | 0.3 |
| gemma | spacex | schema_alter | gemma_e4b | 4.8% | 21637.7 | 0.1 |
| gemma | openweather | qwen | gemma_e4b | 3.3% | 202262.1 | 0.1 |
| gemma | openweather | json_manip | gemma_e4b | 8.8% | 87111.1 | 0.2 |
| gemma | openweather | schema_alter | gemma_e4b | 3.1% | 76931.0 | 0.1 |

### AMD MI250X Quantum Routing Benchmark Results (GPU-Accelerated)

The following are the true mapping results obtained on a LUMI compute node with 2x AMD MI250X GPUs using a dedicated, pre-trained Quantum Router model per API. The routing logic was executed via Qiskit's `AerSimulator` simulator backend, while the reconcilers (including BERT) and Qwen chaos models were fully accelerated in BF16 on the GPUs.

| API | Chaos Method | Routing Strategy | Reconciled Accuracy | Sweep Duration (ms) | Fast Path Overhead (ms) | GPU Latency (ms) |
|:---|:---|:---|:---|:---|:---|:---|
| openweather | schema_alter | quantum_routed | 84.0% | 2906 | 0.34 | 2895 |
| openweather | json_manip | quantum_routed | 84.5% | 5285 | 0.19 | 5275 |
| openf1 | schema_alter | quantum_routed | 93.4% | 40220 | 0.19 | 40203 |
| openf1 | json_manip | quantum_routed | 98.1% | 47262 | 0.18 | 47248 |
| finnhub | schema_alter | quantum_routed | 87.7% | 38097 | 0.20 | 38088 |
| finnhub | json_manip | quantum_routed | 83.9% | 35942 | 0.19 | 35927 |
| spacex | schema_alter | quantum_routed | 97.3% | 4781 | 0.22 | 4767 |
| spacex | json_manip | quantum_routed | 98.8% | 10942 | 0.23 | 10928 |
| openf1 | qwen | quantum_routed | 98.6% | 735227 | 0.17 | 4691 |
| finnhub | qwen | quantum_routed | 76.0% | 745684 | 0.19 | 3856 |
| spacex | qwen | quantum_routed | 98.3% | 721242 | 0.67 | 4445 |
| openweather | qwen | quantum_routed | 85.0% | 722326 | 0.22 | 3350 |

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

## Cloud GPU (Vast.ai / Spheron)

```bash
git clone https://github.com/tarek-clarke/resilient-rap-framework.git && \
  cd resilient-rap-framework && git checkout domain_testing && cd deploy && \
  docker compose -f docker-compose.cloud.yml build rap-cuda && \
  docker compose -f docker-compose.cloud.yml run --rm ingestion && \
  docker compose -f docker-compose.cloud.yml up rap-cuda
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