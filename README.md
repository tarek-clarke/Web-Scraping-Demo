# Resilient RAP Framework

Resilient API Adaptation Protocol (RAP) is a two-stage telemetry reconciliation framework. Clean packets use a CPU schema fast path. Packets with structural drift are sent to a selected reconciliation method, with optional classical, GPU, cloud, simulator, and physical-QPU routing experiments.

The active benchmark corpus contains 22,500 packets from nine API domains. It is a controlled historical replay workload, not a live production capture.

## Current benchmark contract

- 22,500 ordered ingested packets, 2,500 per API domain.
- 20,250 clean packets and 2,250 drifted packets.
- Three deterministic chaos families: `json_manip`, `qwen`, and `schema_alter`.
- Six candidate reconcilers: Levenshtein, Regex, MiniLM, Qwen2.5-1.5B, BGE, and Cohere Embed v4.
- Ten structural features, six route classes, and three VQC output bits.
- The canonical VQC is 13 logical qubits: 10 feature qubits plus 3 output qubits.
- Clean packets bypass reconciliation and are counted separately from drift accuracy.
- All hardware runs must report observed device identity, latency, throughput, energy provenance, and the frozen workload SHA-256.

The canonical route order is fixed in [canonical_vqc.py](src/routing/canonical_vqc.py):

| Class | Method | Tier |
|---:|---|---|
| 0 | `levenshtein` | CPU |
| 1 | `regex` | CPU |
| 2 | `minilm` | Local GPU |
| 3 | `qwen_1_5b` | Local GPU |
| 4 | `bge` | Local GPU |
| 5 | `cohere_embed_v4` | External Cohere API |

## Deterministic stream replay

The source APIs are not called during benchmarking. The committed packet corpus and frozen chaos oracle are combined into one immutable replay artifact. This makes every CPU, GPU, cloud, simulator, and QPU experiment receive the same ordered events and exact ground truth.

Build or rebuild the replay:

```bash
python scripts/build_frozen_telemetry_stream.py \
  --output data/replay/telemetry_frozen_22500_v8.jsonl
```

The generated replay is intentionally ignored by Git and can be rebuilt from the committed corpus and oracle. Its manifest records both source hashes and the workload hash. The current validated workload is:

```text
events:        22,500
clean:         20,250
drifted:        2,250
json_manip:       737
qwen:             746
schema_alter:    767
SHA-256: 9656427b10370559ac4b5ddcfcb1edd97e7cf3a904496d0491275a47ac8f97b3
```

The runner supports two distinct modes:

- `--rate-pps 0`: saturation/capacity replay.
- `--rate-pps N`: paced replay at a declared arrival rate.

These modes must be reported separately. Each method is replayed independently with the same event file. Startup and two warm-up drift packets are timed separately. Steady-state output includes queue wait, service time, end-to-end latency percentiles, backlog, throughput, mapping accuracy, exact-record rate, per-API/per-chaos breakdowns, and host-observed energy.

## Local CPU smoke test

```bash
cd /Users/tarekclarke/Documents/RAP/resilient-rap-framework
RAP_CPU_WORKERS=1 .venv/bin/python scripts/run_frozen_telemetry_stream.py \
  --stream data/replay/telemetry_frozen_22500_v8.jsonl \
  --methods levenshtein regex schema_registry \
  --rate-pps 100 \
  --consumer-batch-size 1 \
  --limit 200 \
  --output-dir data/reports/frozen_stream_cpu_smoke
```

## LUMI execution

Keep caches and runtime state in the project scratch directory:

```bash
cd /scratch/project_465002996/clarketa/resilient-rap-tkde-aer-20260722
bash scripts/bootstrap_lumi_runtime.sh
```

Run CPU methods without allocating an idle GPU:

```bash
sbatch scripts/slurm/submit_frozen_stream_lumi_cpu.slurm
```

Run MiniLM, Qwen, and BGE on a scheduler-bound MI250X GCD:

```bash
sbatch scripts/slurm/submit_frozen_stream_lumi.slurm
```

The LUMI GPU script requires ROCm, exactly one visible scheduler-bound GCD, and a readable AMD power sensor. CPU fallback and missing energy telemetry fail loudly. Three repetitions and a 256-packet accelerator consumer batch are used by default. Qwen retries are generated as batches; they must not be serialized per record. Use the same batch size on GH200 and B300 for hardware comparisons. Override the replay without editing the script:

```bash
RAP_STREAM_RATE_PPS=100 \
RAP_STREAM_REPETITIONS=3 \
RAP_STREAM_OUTPUT_DIR=data/reports/frozen_stream_mi250x_100pps \
sbatch --export=ALL,RAP_STREAM_RATE_PPS,RAP_STREAM_REPETITIONS,RAP_STREAM_OUTPUT_DIR \
  scripts/slurm/submit_frozen_stream_lumi.slurm
```

## NVIDIA GH200 and B300 execution

Run inside the vendor CUDA/PyTorch environment after `scripts/bootstrap_accelerator_env.sh` has completed:

```bash
RAP_HARDWARE_TAG=gh200 bash scripts/run_frozen_stream_nvidia.sh
RAP_HARDWARE_TAG=b300 bash scripts/run_frozen_stream_nvidia.sh
```

The launcher requires CUDA and live NVML power/temperature telemetry. It defaults to MiniLM, Qwen, and BGE; CPU methods should be run through the CPU launcher so their measurements are not mixed with an allocated GPU. Use a paced replay when testing an arrival SLA:

```bash
RAP_HARDWARE_TAG=gh200 \
RAP_STREAM_RATE_PPS=100 \
RAP_STREAM_OUTPUT_DIR=data/reports/frozen_stream_gh200_100pps \
bash scripts/run_frozen_stream_nvidia.sh
```

## Cohere Embed v4

Cohere is an independent cloud baseline and is not a local GPU or QPU measurement. Set the key only in the process environment; never place it in the repository, shell history, README, logs, or `sbatch` command text.

```bash
read -rs COHERE_API_KEY
export COHERE_API_KEY
RAP_COHERE_EMBED_CACHE=0 .venv/bin/python scripts/run_frozen_telemetry_stream.py \
  --stream data/replay/telemetry_frozen_22500_v8.jsonl \
  --methods cohere_embed_v4 \
  --rate-pps 0 \
  --consumer-batch-size 16 \
  --repetitions 3 \
  --hardware-profile cpu \
  --output-dir data/reports/frozen_stream_cohere_embed_v4
unset COHERE_API_KEY
```

Cross-batch Cohere embedding caching is disabled by default so network latency is measured on the stream. `--allow-cohere-cache` is a separate deployment-cache experiment and must be labeled separately. Client-side network latency and host energy are observable; Cohere server-side energy is not available through the API and must not be inferred.

## Artifacts

Every completed replay writes:

- `benchmark.json`: run identity, hardware, workload hash, configuration, summary, and energy provenance.
- `packet_results.jsonl`: one row per packet and method, including queue and end-to-end timings.
- `summary.csv`: aggregate method metrics.
- `breakdown.csv`: API and chaos-family metrics.
- `summary.tex`: LaTeX-compatible aggregate table.
- `energy_<method>_rep<N>.csv`: host power samples for each method repetition.

Only artifacts with `status: complete`, the expected workload hash, explicit hardware identity, and energy measurement provenance are publication-ready.

## Routing and quantum execution

The reconciliation stream benchmark is separate from router evaluation. Once the method artifacts are complete, the same frozen workload and selected model can be used for:

- Aer simulation on ROCm or CUDA.
- IBM Heron r2 execution through the existing QPU runner.
- VLQ execution after the LEXIS/HEAppE service is operational.

The physical QPU result must use the canonical 13-qubit circuit and must not be described as comparable to older 12-qubit IBM runs. QPU server-side energy is not observable through the provider API. Router-selection accuracy and routed end-to-end reconciliation accuracy must be reported as separate metrics.

## Data and code layout

```text
data/ingested/telemetry_clean_bench_22500.json   # retained source corpus
data/training/router_oracle_22500_v8_qwen_10pct_single.jsonl
scripts/build_frozen_telemetry_stream.py          # deterministic workload builder
scripts/run_frozen_telemetry_stream.py            # event-driven benchmark
scripts/run_frozen_stream_nvidia.sh               # GH200/B300 launcher
scripts/slurm/submit_frozen_stream_lumi.slurm     # LUMI GPU launcher
scripts/slurm/submit_frozen_stream_lumi_cpu.slurm # LUMI CPU launcher
src/reconciliation/                                # method implementations
src/routing/canonical_vqc.py                       # 13-qubit protocol
src/telemetry/metrics_logger.py                    # host energy telemetry
```

Historical experiments and superseded result tables are not part of the active README. The ingested corpus is retained; generated replay outputs and benchmark reports are rebuilt per run.
