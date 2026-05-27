# Semantic Drift Evaluation Pipeline

Cross-platform benchmark for semantic schema drift detection and reconciliation
using BERT embeddings and Gemma-4 E4B, evaluated under controlled chaos injection
on real-world API schemas (Finnhub, OpenMeteo, SpaceX, OpenF1).

## Results

| Metric | Apple M4 (MPS) | AMD RX 7900 XT (ROCm) |
|--------|----------------|----------------------|
| Detection rate (cold) | 1.0 | 0.8859 |
| p95 latency (cold) | 120.0 ms | 4397.92 ms |
| Detection rate (stable) | 1.0 | 0.8856 |
| p95 latency (stable) | 117.0 ms | 4392.39 ms |
| Total runs | 864 | 815 |
| Global runtime | 418.9352 s | 11893.95 s |

## Raw Platform Summaries

These summaries are computed from the per-platform raw artifacts in `results/raw/` and are meant for paper drafting and evaluation.

| Device token | Readable label |
|--------------|----------------|
| `Apple_Silicon_arm` | Apple M4 16GB |
| `aarch64` | GH200 |
| `NVIDIA_GeForce_RTX_5090` | NVIDIA RTX 5090 |
| `AMD_Radeon_RX_7900_XT` | AMD RX 7900 XT |

| Platform | Raw files | Baseline runs | Full runs | Mean detection rate | Mean p95 latency | Mean recovery score | Mean resilience P / P2 | Fallback used |
|----------|-----------|---------------|-----------|---------------------|------------------|---------------------|------------------------|---------------|
| Apple M4 16GB | 1100 | 20 | 1080 | 0.8682 | 207.984 ms | 0.9817 | 0.4295 / 0.5187 | 0 |
| GH200 | 1100 | 20 | 1080 | 0.8755 | 7.693 ms | 0.9777 | 0.7360 / 0.7628 | 0 |
| NVIDIA RTX 5090 | 1100 | 20 | 1080 | 0.8645 | 23.877 ms | 0.9774 | 0.6435 / 0.6881 | 0 |

### Quick Read

- Apple M4 16GB is the clearest MPS reference point: good recovery, but much higher latency than the CUDA platforms.
- GH200 is the lowest-latency platform in the current raw set and is a strong candidate for the fastest-deployment comparison.
- NVIDIA RTX 5090 sits between the two on latency while staying competitive on recovery and resilience.
- Across these raw runs, `fallback_used` stayed at zero, so the measured behavior reflects the normal repair pipeline rather than BERT fallback.

### Ablation Study

| Condition | Detection Rate (mean � ci95) | p95 Latency (mean � ci95) | Resilience P (mean � ci95) |
|-----------|------|------|------|
| full_pipeline | 0.8859 � 0.0218 | 4397.92 � 466.40 ms | 0.4639 � 0.0058 |
| ablation_no_bert | 0.8775 � 0.0319 | 4241.14 � 635.30 ms | 0.4309 � 0.0122 |
| ablation_no_gemma | 0.8846 � 0.0307 | 4489.44 � 638.53 ms | 0.4625 � 0.0082 |
| ablation_fast_only | 0.8854 � 0.0305 | 4520.06 � 639.05 ms | 0.4103 � 0.0102 |
| baseline_no_chaos | 0.0000 � 0.0000 | 55.80 � 3.01 ms | 0.2984 � 0.0043 |

## Methodology

- **864 configurations**: 2 packet profiles � 3 frequencies � 3 chaos strategies � 3 levels � 4 APIs, 4 runs each
- **Chaos strategies**: JSON mutation, schema drift, Gemma-generated adversarial mutations
- **Reconcilers**: Levenshtein distance, regex, BERT semantic similarity (all-MiniLM-L6-v2), Gemma-4 E4B
- **Metrics**: Detection rate, p95 latency, repair rate, recovery score, resilience P/P2

## Raw Run Methodology

- **Raw generation mode**: run `python run_all.py --generate-only` to write per-run JSON artifacts.
- **Destination**: artifacts are written to `results/raw/<hardware_token>/`.
- **Cross-platform policy**: keep one hardware token folder per platform (HPC/CUDA, Apple Silicon/MPS, consumer GPU/ROCm or CUDA).
- **Raw filename schema**: `run_{run:03d}_{api}_{packet}_{freq}_{chaos}_{level}_{hardware}_{drift_or_clean}.json`.
- **Baseline filename schema**: `baseline_run_{run:03d}_{api}_{packet}_{freq}_{chaos}_{level}_{hardware}_{drift_or_clean}.json`.
- **Baseline minimum policy**: baseline clean pipeline is topped up to at least 5 runs per baseline config by default (`--min-baseline-runs`).
- **Run-count policy**: standard phases are controlled by `--runs-per-config` and tagged with `policy_tag` metadata.
- **Stable metric policy**: stable means exclude run 1 and summarize runs 2..N.
- **Provenance policy**: each run record carries `policy` + `policy_tag` metadata for reproducibility tracking.
- **Analysis workflow**: analyze each platform independently via `python analyze.py --data-dir results/raw/<hardware_token>`.

## New Cloud Instance Quickstart

Use this on a fresh Linux cloud VM/instance. It clones the repo, builds a venv, installs deps,
checks that the backend is GPU-enabled, runs top-up generation without erasing existing outputs,
and runs post-hoc analysis.

```bash
set -euo pipefail

git clone https://github.com/tarek-clarke/resilient-rap-framework.git
cd resilient-rap-framework
git checkout semantic_only

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Verify backend (ROCm/CUDA should report available=True)
python - <<'PY'
import torch
from models.device_selector import get_device_info
print('torch', torch.__version__)
print('cuda_available', torch.cuda.is_available())
print('hip', getattr(torch.version, 'hip', None))
print(get_device_info())
PY

# Keep existing outputs and fill only missing runs
printf 'N\n' | python run_all.py --generate-only

# Recompute summary metrics from raw files for this hardware folder
HW_TOKEN=$(python - <<'PY'
from models.device_selector import get_device_info
v = get_device_info().get('model', 'unknown')
print(v.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', ''))
PY
)
python analyze.py --data-dir "results/raw/${HW_TOKEN}"
```

If your cloud image has a CPU-only PyTorch wheel, install the correct ROCm or CUDA wheel first,
then rerun the backend verification block above.

## Apple Silicon Rerun

Use this on your Macbook when you want to wipe the Apple figures and rebuild raw data in the same style as the AMD 7900 XT and NVIDIA 5090 runs.

```bash
set -euo pipefail

cd /Users/tarekclarke/resilient-rap-clean/resilient-rap-semantic

# Optional: wipe the old Apple summary/figure outputs
rm -rf results/Apple_Silicon_arm

# Regenerate raw Apple Silicon records and top up missing runs to 5 per profile
python3 run_all.py --generate-only

# If you also want the non-raw summaries/ablation outputs, run the full pipeline instead:
# python3 run_all.py
```

Notes:
- Leave the erase prompt as `N` if you want to keep any existing raw records and only fill missing runs.
- Do not pass `--skip-git-push` if you want the run to auto-push to GitHub when it finishes.
- `--generate-only` writes the raw per-run JSONs under `results/raw/Apple_Silicon_arm/` and avoids redoing completed profiles.
- The default run policy now targets 5 runs per profile, so if Apple raw already has runs 1..3, it will only compute runs 4 and 5.

## Hardware

| Platform | GPU | Memory | Precision |
|----------|-----|--------|-----------|
| Apple M4 16GB | M4 (MPS) | Unified | float16 |
| GH200 | Hopper (CUDA) | 96 GB | bfloat16 |
| NVIDIA RTX 5090 | RTX 5090 (CUDA) | 32 GB | float16 |
| AMD ROCm | RX 7900 XT (gfx1100) | 20 GB | bfloat16 |
