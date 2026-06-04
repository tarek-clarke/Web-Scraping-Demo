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
- contextual_rename, synonym_substitution, abbreviation_expand, abbreviation_contract, unit_semantic_shift, domain_terminology

### 2. JSON Manipulation (Structure/Value)
- field_split, field_join, variable_drop, field_merge_value, array_to_scalar, scalar_to_array, array_expansion, duplicate_field_inject, null_injection, default_value_inject, outlier_injection

### 3. Schema Alteration (Type/Structure/Temporal)
- translation, type_change, precision_loss, unit_conversion, nesting_flatten, nesting_deepen, timestamp_format_change, timezone_change, date_format_change, encoding_change, key_case_change, array_index_rename

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