# Resilient RAP Framework

Resilient API Adaptation Protocol (RAP) is a two-stage schema-reconciliation framework. Clean records use a CPU fast path. Structurally drifted records are routed to one of eight CPU, local-accelerator, or cloud reconciliation methods by a 13-qubit VQC.

## Active publication protocol (v9)

The v9 corpus is an immutable snapshot of exactly 22,500 real API records: 2,500 distinct payloads from each source. Mock records, repeated padding, API fallback data, and silently partial pulls are forbidden.

| Source ID | Public API data |
|---|---|
| `openf1` | Historical Formula 1 car data |
| `binance_market` | Historical BTC/USDT minute bars |
| `noaa_space_weather` | NOAA SWPC solar-wind plasma observations |
| `openmeteo_weather` | Historical hourly weather observations |
| `openfda_adverse_events` | FDA adverse-event reports (FAERS; not ICU telemetry) |
| `hockey_nhl` | NHL play-by-play events |
| `aviation_opensky` | OpenSky aircraft state vectors |
| `football_openligadb` | OpenLigaDB football matches |
| `smartcity_mbta` | MBTA transit stop records |

The API snapshot is historical/frozen and is replayed as a stream. It is not represented as nine simultaneously captured live feeds. OpenFDA is a pharmacovigilance source and must not be described as ICU monitoring.

Ten percent of records are selected deterministically for drift. The `json_manip` and `schema_alter` families are seeded rule-based transformations. The `qwen` family is generated once on LUMI-G by `Qwen/Qwen2.5-1.5B-Instruct`, validated, saved, and reused. Qwen is never rerun independently on each hardware platform.

All eight three-bit states are used:

| Bits | Route | Tier |
|---|---|---|
| `000` | `levenshtein` | CPU |
| `001` | `regex` | CPU |
| `010` | `schema_registry` | CPU |
| `011` | `minilm` | Local GPU |
| `100` | `qwen_1_5b` | Local GPU |
| `101` | `bge` | Local GPU |
| `110` | `cross_encoder` | Local GPU |
| `111` | `cohere_embed_v4` | External API |

The VQC remains 13 logical qubits: ten feature qubits and three measured output qubits. Abstention is an optional confidence threshold applied after decoding; it does not consume an output state.

## Stage 1 — pull and freeze the real API corpus

Run this once on a networked workstation. `OPENFDA_API_KEY` is optional but improves FDA rate limits. The command refuses to overwrite an existing snapshot unless `--overwrite` is supplied.

```bash
git clone --branch tkde git@github.com:tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework

python3 scripts/pull_real_api_snapshot.py \
  --output data/ingested/telemetry_real_api_22500_v1.json
```

The adjacent manifest records record counts, per-source uniqueness, source IDs, and the snapshot SHA-256. A publication run is valid only when `publication_ready` is `true` and every source has 2,500 distinct IDs and payload hashes.

The independently captured openFDA component is stored as:

```text
data/ingested/openfda_adverse_events_2500_v1.json
data/ingested/openfda_adverse_events_2500_v1.manifest.json
```

## Stage 2 — LUMI-G Qwen drift, oracle, and MI250X runs

Copy the immutable corpus to LUMI scratch; do not store model caches or benchmark data in `$HOME`.

```bash
# On the Mac
scp data/ingested/telemetry_real_api_22500_v1.json* \
  clarketa@lumi.csc.fi:/scratch/project_465002996/clarketa/resilient-rap-tkde-aer-20260722/data/ingested/

# Connect to LUMI
ssh -i ~/.ssh/id_ed25519 clarketa@lumi.csc.fi
cd /scratch/project_465002996/clarketa/resilient-rap-tkde-aer-20260722
git pull --ff-only origin tkde
bash scripts/bootstrap_lumi_runtime.sh
```

Generate model-backed Qwen chaos once on a scheduler-bound MI250X GCD:

```bash
sbatch scripts/slurm/generate_qwen_chaos_v9.slurm
```

Check that it completed before training:

```bash
sacct -j JOB_ID --format=JobID,State,Elapsed,ExitCode
cat data/training/qwen_model_chaos_22500_v1.manifest.json
```

Run the eight-method oracle and ten independent VQC training starts. Cohere is a route, so load its key without echoing or writing it to disk:

```bash
read -rs COHERE_API_KEY
export COHERE_API_KEY
export ORACLE_METHODS="levenshtein regex schema_registry minilm qwen_1_5b bge cross_encoder cohere_embed_v4"
LUMI_GPU_PROFILE=single bash scripts/slurm/submit_qpu_training_pipeline.sh
unset COHERE_API_KEY
```

After the oracle is complete, build the one frozen replay used everywhere:

```bash
python scripts/build_frozen_telemetry_stream.py \
  --packets data/ingested/telemetry_real_api_22500_v1.json \
  --oracle data/training/router_oracle_22500_v9_eight_route_10pct_single.jsonl \
  --output data/replay/telemetry_frozen_22500_v9.jsonl
```

Run CPU routes on a CPU allocation and accelerator routes on MI250X. CPU fallback and missing GPU telemetry fail loudly.

```bash
sbatch scripts/slurm/submit_frozen_stream_lumi_cpu.slurm
sbatch scripts/slurm/submit_frozen_stream_lumi.slurm
```

The default local-GPU methods are MiniLM, Qwen, BGE, and the cross-encoder. For a four-card/8-GCD data-parallel measurement, use the sharded launcher and label it separately from the one-GCD run:

```bash
RAP_STREAM_FILE=data/replay/telemetry_frozen_22500_v9.jsonl \
RAP_STREAM_METHODS="minilm qwen_1_5b bge cross_encoder" \
RAP_STREAM_OUTPUT_DIR=data/reports/v9_mi250x_4card \
sbatch --export=ALL,RAP_STREAM_FILE,RAP_STREAM_METHODS,RAP_STREAM_OUTPUT_DIR \
  scripts/slurm/submit_frozen_stream_lumi_4card.slurm
```

## Stage 3 — GH200 and B300 on Spheron

Use the same repository commit, frozen JSONL, manifest, model artifact, batch size, repetitions, and software versions on both NVIDIA machines. Do not regenerate chaos or repull APIs.

```bash
# On each Spheron instance
git clone --branch tkde git@github.com:tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
bash scripts/bootstrap_accelerator_env.sh
```

Copy the frozen workload from the Mac or LUMI results download:

```bash
# On the Mac; replace HOST and USER as needed
scp data/replay/telemetry_frozen_22500_v9.jsonl* USER@HOST:/path/to/resilient-rap-framework/data/replay/
```

Run one GPU per instance:

```bash
# GH200
RAP_HARDWARE_TAG=gh200 \
RAP_STREAM_BATCH_SIZE=256 \
RAP_STREAM_REPETITIONS=3 \
bash scripts/run_frozen_stream_nvidia.sh

# B300
RAP_HARDWARE_TAG=b300 \
RAP_STREAM_BATCH_SIZE=256 \
RAP_STREAM_REPETITIONS=3 \
bash scripts/run_frozen_stream_nvidia.sh
```

CPU methods must be run separately and identified by host CPU; their values are not GPU measurements. Cohere is also run separately because it measures client/network behavior, not GH200, B300, or MI250X compute.

## Publication checks

Every publishable run must contain:

- the same frozen-workload SHA-256;
- exactly 22,500 events and 2,250 deterministic drift cases;
- explicit device and host identities;
- no CPU fallback for GPU methods;
- three or more repetitions with identical configuration;
- latency, throughput, accuracy, queueing, and host-observed energy provenance;
- a complete status marker and generated CSV/JSON/LaTeX summaries.

All v8 results derived from `telemetry_clean_bench_22500.json` are archived and must not be mixed with v9 tables. The manuscript must be updated from six routes plus abstention to eight routes, replace the old nine-domain list, remove ICU claims, and regenerate every accuracy, routing-distribution, statistical, energy, and hardware-comparison table from v9 outputs.

## Active files

```text
src/benchmark_protocol.py                         # source contract
src/routing/canonical_vqc.py                     # 13q / eight-route VQC
scripts/pull_real_api_snapshot.py                # strict real API snapshot
scripts/build_qwen_chaos_snapshot.py             # one-time model-backed chaos
scripts/build_router_oracle.py                   # eight-method oracle
scripts/build_frozen_telemetry_stream.py          # immutable replay
scripts/run_frozen_telemetry_stream.py            # hardware benchmark
scripts/slurm/generate_qwen_chaos_v9.slurm       # LUMI Qwen generation
scripts/slurm/submit_frozen_stream_lumi.slurm     # MI250X
scripts/run_frozen_stream_nvidia.sh               # GH200/B300
```
