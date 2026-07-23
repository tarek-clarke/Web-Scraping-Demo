# Canonical single-job QPU workflow

This is the active paper workflow for the 9-API, 22,500-packet corpus. It
replaces the legacy 81-job matrix and shadow-replay paths.

If you are restarting from scratch, archive the benchmark outputs only
(`data/reports/`, `data/training/qpu_router_multistart_v2/`, the frozen oracle
files, and the selected router configs). Keep the ingested corpus in
`data/ingested/` in place.

## What changed

- Stage 1 compares packet schemas, not changing telemetry values.
- Stage 2 is one versioned 12-qubit circuit: 10 feature qubits, 2 measured
  routing qubits, 2 data-reuploading/ansatz repetitions, and 24 trainable
  weights.
- Training and hardware inference use the same unitary and bit-to-class map.
- Labels are packet-level, cost-aware oracle labels from all four reconcilers.
- Ten independent simulator starts train concurrently on up to ten LUMI GPUs.
  Selection uses validation macro-F1; the held-out test split is opened once.
- A minimum 0.70 held-out macro-F1 and 0.70 balanced accuracy is enforced
  before physical-QPU submission.
- IBM uses one `SamplerV2.run` call containing one parameterized PUB.
- VLQ uses one QaaS `backend.run` call containing the same frozen workload.
- Legacy physical submission entry points fail loudly.

The logical model stays at 12 qubits. The 156-qubit IBM and 24-qubit VLQ
devices provide placement/routing capacity; increasing the logical width would
change the model and make the provider results incomparable.

## 1. Train on LUMI

From the LUMI repository:

```bash
cd /scratch/project_465002996/clarketa/resilient-rap-tkde-aer-20260722
bash scripts/slurm/submit_qpu_training_pipeline.sh
```

If the packet-level oracle is absent, the launcher first schedules its
resumable GPU build. It then schedules:

1. a Slurm array of 10 independent training starts (`0-9`), one GPU each;
2. one dependent selection job that writes `configs/quantum_router_v2.json`.

The script prints all Slurm IDs and submits no physical-QPU work. Re-running
does not overwrite completed candidates unless `--overwrite` is deliberately
used.

## 2. Freeze two identical provider bundles

Run these after copying/pulling the selected model and oracle to the Mac:

```bash
python3 scripts/run_qpu_router_experiment.py prepare \
  --oracle data/training/router_oracle_22500_v2.jsonl \
  --model configs/quantum_router_v2.json \
  --run-name ibm_heron_r2_run01 \
  --run-dir data/reports/qpu_router_20260723_ibm_run01 \
  --repetitions 3 \
  --shots 384

python3 scripts/run_qpu_router_experiment.py prepare \
  --oracle data/training/router_oracle_22500_v2.jsonl \
  --model configs/quantum_router_v2.json \
  --run-name vlq_run01 \
  --run-dir data/reports/qpu_router_20260723_vlq_run01 \
  --repetitions 3 \
  --shots 384
```

Both manifests must report the same `model_sha256`, `oracle_sha256`, and
`workload_sha256`. Separate directories prevent an accidental second provider
submission from the same bundle.

The default held-out workload has 6,750 cases (9 APIs × 250 held-out packet
identities × 3 chaos methods). Three technical replicates at 384 shots produce
20,250 parameter sets and 7,776,000 circuit-shots, below IBM's 10,000,000
execution limit.

## 3. IBM 156-qubit Heron r2

```bash
python3 scripts/run_qpu_router_experiment.py submit-ibm \
  --run-dir data/reports/qpu_router_20260723_ibm_run01 \
  --backend-name auto-heron-r2
```

The selector refuses anything other than an operational 156-qubit Heron r2.
It generates 16 optimization-level-3 transpilation candidates, scores their
calibration-aware gate quality/depth, enables XpXm dynamical decoupling plus
gate/measurement twirling, and performs exactly one provider submission.

Do not pass `--wait`; the job continues after the laptop closes. Retrieve it:

```bash
python3 scripts/run_qpu_router_experiment.py retrieve-ibm \
  --run-dir data/reports/qpu_router_20260723_ibm_run01
```

## 4. VLQ 24-qubit star QPU

After IT4I confirms access:

```bash
python3 scripts/smoke_test_vlq_qpu.py

python3 scripts/run_qpu_router_experiment.py submit-vlq \
  --run-dir data/reports/qpu_router_20260723_vlq_run01
```

The runner compiles the same logical circuit to the live VLQ target and makes
one QaaS submission. Retrieve it with:

```bash
python3 scripts/run_qpu_router_experiment.py retrieve-vlq \
  --run-dir data/reports/qpu_router_20260723_vlq_run01
```

At the documented conservative VLQ accounting bound of 400 microseconds per
shot, 7,776,000 circuit-shots are approximately 51.84 minutes, before any
provider-specific minimums/overhead. This is an estimate, not observed energy.

## Outputs

Each completed provider directory contains:

- immutable model/workload hashes and experiment manifest;
- submitted job ID, backend, runtime options, and transpilation candidates;
- compiled QPY circuit;
- provider-reported job/usage metrics;
- client-host wall time, CPU time, and peak resident memory;
- per-case counts, probabilities, predictions, technical replicates, and
  ensemble decision in JSONL and CSV;
- per-API/per-chaos summaries and confusion matrices;
- paper-ready result and configuration tables (`.tex`).

IBM and QaaS do not expose remote QPU electricity or carbon through these
APIs. Provider QPU usage is therefore reported separately from client-host
observations; the workflow does not invent a remote energy estimate.

## Experimental interpretation

The three repeats inside one job are technical shot replicates under one
calibration window. They improve uncertainty reporting but are not three
independent hardware experiments. If additional budget is later available,
prepare new run directories and repeat on different dates/calibrations. Do not
train on the held-out QPU result or choose the best hardware run post hoc.
