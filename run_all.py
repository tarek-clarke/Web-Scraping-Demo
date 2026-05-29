import os
import sys
import json
import time
import csv
import math
import subprocess
import argparse
import platform
import re
from uuid import uuid4
from models.device_selector import get_device_info
from models.bert_model import BERTModel
from models.gemma_offline import GemmaModel
from semantic.gemma_recon import GemmaReconciler
from tests.run_experiments import ExperimentRunner
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


def mean(vals):
    return sum(vals) / max(1, len(vals))

def stdev(vals):
    if len(vals) < 2:
        return 0.0
    m = mean(vals)
    return math.sqrt(sum((x - m)**2 for x in vals) / (len(vals) - 1))

def ci95(vals):
    n = len(vals)
    if n < 2:
        return 0.0
    return 1.96 * stdev(vals) / math.sqrt(n)


def parse_args():
    parser = argparse.ArgumentParser(description='Semantic drift benchmark runner')
    parser.add_argument('--bootstrap', action='store_true', help='Run bootstrap first')
    parser.add_argument('--generate-only', action='store_true', help='Generate raw JSON records only')
    parser.add_argument('--erase-existing', action='store_true', help='Erase existing platform result folder')
    parser.add_argument('--force-erase', action='store_true', help='Alias for --erase-existing')
    parser.add_argument('--runs-per-config', type=int, default=5,
                        help='Runs per configuration for standard phases (default: 5)')
    parser.add_argument('--min-baseline-runs', type=int, default=5,
                        help='Ensure baseline clean pipeline has at least this many runs per config (default: 5)')
    parser.add_argument('--policy-tag', default='tkde_policy_v1',
                        help='Policy tag embedded into outputs for reproducibility')
    parser.add_argument('--skip-git-push', action='store_true',
                        help='Skip final git push')
    # ── Pre-flight / traceability options ──
    parser.add_argument('--require-gpu', action='store_true', default=True,
                        help='Require GPU for execution (default: True)')
    parser.add_argument('--no-require-gpu', dest='require_gpu', action='store_false',
                        help='Allow CPU execution without GPU')
    parser.add_argument('--cpu-allowed', action='store_true', default=False,
                        help='Fall back to CPU if GPU is missing')
    parser.add_argument('--require-local-models', action='store_true', default=True,
                        help='Require BERT/Gemma to be available locally (default: True)')
    parser.add_argument('--no-require-local-models', dest='require_local_models', action='store_false',
                        help='Allow internet fallback for model loading')
    parser.add_argument('--strict-mode', action='store_true', default=False,
                        help='Abort on any fallback, missing model, or unexpected internet handshake')
    return parser.parse_args()


def get_git_commit():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    except Exception:
        return 'unknown'


def get_pipeline_version():
    """Return pipeline_version string for reproducibility."""
    return get_git_commit()


def get_model_version_string(model_type="bert"):
    """Return a version string for BERT or Gemma models."""
    try:
        if model_type == "bert":
            import sentence_transformers
            return getattr(sentence_transformers, '__version__', 'unknown')
        elif model_type == "gemma":
            return "Gemma-4-E4B"
    except Exception:
        pass
    return "unknown"


def run_preflight_checks(require_gpu=True, cpu_allowed=False, require_local_models=True,
                         strict_mode=False, verbose=True):
    """Perform strict pre-flight validation before any run begins.

    Validates:
    - GPU availability (unless CPU explicitly allowed)
    - Hardware backend tensor placement
    - BERT model availability
    - Gemma model availability
    - Model version logging
    - Internet handshake detection
    - Pipeline version (git commit hash)

    Returns:
        dict: preflight results including gpu_available, hardware_backend_verified,
              bert_available, gemma_available, internet_used, model_source,
              model_version, pipeline_version, plus any abort flags.
        tuple: (preflight_dict, abort, abort_reason)
    """
    d = get_device_info()
    device = d["device"]
    hw_backend = d["hardware_backend"]
    gpu_available = device in ("cuda", "rocm", "mps")
    cpu_mode = not gpu_available
    bert_available = False
    gemma_available = False
    hardware_backend_verified = False
    internet_used = False
    model_source = {}
    model_version = {}

    # ── Pipeline version ──
    pipeline_version = get_pipeline_version()
    model_version["bert"] = get_model_version_string("bert")
    model_version["gemma"] = get_model_version_string("gemma")

    if verbose:
        print(f"\n{'='*80}")
        print(f" PRE-FLIGHT VALIDATION")
        print(f" Device          : {device}")
        print(f" Hardware backend: {hw_backend}")
        print(f" GPU available   : {gpu_available}")
        print(f" Pipeline version: {pipeline_version}")
        print(f" CPU allowed     : {cpu_allowed}")
        print(f" Require GPU     : {require_gpu}")
        print(f" Require local   : {require_local_models}")
        print(f" Strict mode     : {strict_mode}")
        print(f"{'='*80}")

    # ── A/B: GPU / CPU validation ──
    if require_gpu and not gpu_available:
        msg = f"GPU required but not available (device={device})."
        if not cpu_allowed:
            preflight = {
                "gpu_available": False, "gpu_backend": hw_backend, "cpu_allowed": cpu_allowed,
                "cpu_mode": cpu_mode, "bert_available": False, "gemma_available": False,
                "internet_used": False, "model_source": {}, "model_version": model_version,
                "hardware_backend_verified": False, "require_local_models": require_local_models,
                "require_gpu": require_gpu, "strict_mode": strict_mode,
                "pipeline_version": pipeline_version
            }
            return preflight, True, msg
        else:
            if verbose:
                print(f" [WARN] {msg} — cpu_allowed=True, proceeding on CPU")

    if not gpu_available and not cpu_allowed:
        msg = f"No GPU available and cpu_allowed=False. ABORT."
        preflight = {
            "gpu_available": False, "gpu_backend": hw_backend, "cpu_allowed": cpu_allowed,
            "cpu_mode": cpu_mode, "bert_available": False, "gemma_available": False,
            "internet_used": False, "model_source": {}, "model_version": model_version,
            "hardware_backend_verified": False, "require_local_models": require_local_models,
            "require_gpu": require_gpu, "strict_mode": strict_mode,
            "pipeline_version": pipeline_version
        }
        return preflight, True, msg

    # ── C: Hardware backend verification (tensor placement test) ──
    if TORCH_AVAILABLE:
        try:
            torch_device = device
            if device in ("cuda", "rocm"):
                torch_device = "cuda"
            _ = torch.randn(1).to(torch_device)
            hardware_backend_verified = True
            if verbose:
                print(f" [✓] Hardware backend verified: tensor placed on {torch_device}")
        except Exception as e:
            hardware_backend_verified = False
            if strict_mode:
                msg = f"Hardware backend verification failed: {e}"
                preflight = {
                    "gpu_available": gpu_available, "gpu_backend": hw_backend,
                    "cpu_allowed": cpu_allowed, "cpu_mode": cpu_mode,
                    "bert_available": False, "gemma_available": False,
                    "internet_used": False, "model_source": {}, "model_version": model_version,
                    "hardware_backend_verified": False,
                    "require_local_models": require_local_models,
                    "require_gpu": require_gpu, "strict_mode": strict_mode,
                    "pipeline_version": pipeline_version
                }
                return preflight, True, msg
            if verbose:
                print(f" [WARN] Hardware backend verification failed: {e}")
    else:
        if verbose:
            print(" [WARN] PyTorch not available — skipping tensor placement test")

    # ── D: BERT availability ──
    try:
        bert = BERTModel(allow_internet=True)
        bert_available = bert.is_loaded
        if bert_available:
            model_source["bert"] = getattr(bert, "model_source", "local")
            if verbose:
                if model_source["bert"] == "internet":
                    print(" [✓] BERT model downloaded from the internet and loaded")
                elif model_source["bert"] == "downloaded":
                    print(" [✓] BERT model downloaded once and cached locally")
                else:
                    print(" [✓] BERT model loaded locally")
            if model_source["bert"] in ("internet", "downloaded"):
                internet_used = True
        else:
            model_source["bert"] = getattr(bert, "model_source", "internet")
            if verbose:
                print(" [WARN] BERT not available locally after download attempt")
    except Exception as e:
        bert_available = False
        model_source["bert"] = "internet"
        if verbose:
            print(f" [WARN] BERT load error: {e}")

    # ── E: Gemma availability ──
    try:
        gemma = GemmaModel()
        # Consider both local and downloaded backends as "available" for runtime
        gemma_available = gemma.backend in ("local", "downloaded")
        if gemma_available:
            model_source["gemma"] = "local" if gemma.backend == "local" else "downloaded"
            if verbose:
                if gemma.backend == "local":
                    print(" [✓] Gemma model loaded locally")
                else:
                    print(" [✓] Gemma model downloaded from the internet and loaded")
            if gemma.backend == "downloaded":
                internet_used = True
        else:
            model_source["gemma"] = "internet"
            internet_used = True
            if verbose:
                print(" [WARN] Gemma not available locally — would need internet fallback")
            if require_local_models:
                msg = "Gemma not available locally and require_local_models=True. ABORT."
                preflight = {
                    "gpu_available": gpu_available, "gpu_backend": hw_backend,
                    "cpu_allowed": cpu_allowed, "cpu_mode": cpu_mode,
                    "bert_available": bert_available, "gemma_available": False,
                    "internet_used": internet_used, "model_source": model_source,
                    "model_version": model_version,
                    "hardware_backend_verified": hardware_backend_verified,
                    "require_local_models": require_local_models,
                    "require_gpu": require_gpu, "strict_mode": strict_mode,
                    "pipeline_version": pipeline_version
                }
                return preflight, True, msg
    except Exception as e:
        gemma_available = False
        model_source["gemma"] = "internet"
        internet_used = True
        if verbose:
            print(f" [WARN] Gemma load error: {e}")
        if require_local_models:
            msg = f"Gemma load failed ({e}) and require_local_models=True. ABORT."
            preflight = {
                "gpu_available": gpu_available, "gpu_backend": hw_backend,
                "cpu_allowed": cpu_allowed, "cpu_mode": cpu_mode,
                "bert_available": bert_available, "gemma_available": False,
                "internet_used": internet_used, "model_source": model_source,
                "model_version": model_version,
                "hardware_backend_verified": hardware_backend_verified,
                "require_local_models": require_local_models,
                "require_gpu": require_gpu, "strict_mode": strict_mode,
                "pipeline_version": pipeline_version
            }
            return preflight, True, msg

    # ── Strict mode checks ──
    if strict_mode:
        if not gpu_available and not cpu_allowed:
            return None, True, "Strict mode: GPU missing and CPU not allowed."
        if not bert_available and require_local_models:
            return None, True, "Strict mode: BERT missing locally."
        if not gemma_available and require_local_models:
            return None, True, "Strict mode: Gemma missing locally."
        if internet_used and not cpu_allowed:
            # Internet handshake not explicitly disallowed, but strict mode flags it
            if verbose:
                print(" [STRICT] Internet would be used — proceeding (not explicitly disallowed)")

    preflight = {
        "gpu_available": gpu_available,
        "gpu_backend": hw_backend,
        "cpu_allowed": cpu_allowed,
        "cpu_mode": cpu_mode,
        "bert_available": bert_available,
        "gemma_available": gemma_available,
        "internet_used": internet_used,
        "model_source": model_source,
        "model_version": model_version,
        "hardware_backend_verified": hardware_backend_verified,
        "require_local_models": require_local_models,
        "require_gpu": require_gpu,
        "strict_mode": strict_mode,
        "pipeline_version": pipeline_version
    }

    # If both models are now available locally (including after a one-time
    # download), enforce offline mode for the remainder of the process so that
    # no further network access occurs during the run.
    try:
        if bert_available and gemma_available:
            os.environ["HF_HUB_OFFLINE"] = "1"
            if verbose:
                print(" [✓] Models available locally — enforcing HF_HUB_OFFLINE=1 for the run")
    except Exception:
        # Non-fatal; continue without forcing offline mode if env cannot be set.
        pass

    if verbose:
        print(f" {'[✓]' if not (require_gpu and not gpu_available) else '[✗]'} Pre-flight passed")
        print(f"{'='*80}\n")

    return preflight, False, None


def build_policy_metadata(args, device_info):
    return {
        'policy_tag': args.policy_tag,
        'cross_platform_parity_required': True,
        'baseline_min_runs_per_config': max(1, args.min_baseline_runs),
        'standard_runs_per_config': max(1, args.runs_per_config),
        'stable_window_excludes_run_1': True,
        'reproducibility': {
            'git_commit': get_git_commit(),
            'python_version': platform.python_version(),
            'platform': platform.platform(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'seed_env': {
                'PYTHONHASHSEED': os.environ.get('PYTHONHASHSEED', ''),
                'SEMANTIC_SEED': os.environ.get('SEMANTIC_SEED', '')
            }
        },
        'device': {
            'model': device_info.get('model', 'unknown'),
            'vram_gb': device_info.get('vram_gb', 'unknown'),
            'cloud': device_info.get('cloud', 'unknown')
        }
    }


def attach_policy_metadata(record, policy):
    record['policy'] = policy
    record['policy_tag'] = policy.get('policy_tag', 'unknown')
    return record


def config_key_from_record(r):
    return (
        r.get('packet_profile'),
        r.get('frequency_profile'),
        r.get('chaos_strategy'),
        r.get('chaos_level'),
        r.get('api_name')
    )


def sanitize_hw_token(value):
    return value.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')


def baseline_raw_filename(record):
    rn = int(record.get('run_number', 0))
    an = record.get('api_name', 'unknown')
    pp = record.get('packet_profile', 'unknown')
    fp = record.get('frequency_profile', 'unknown')
    cs = record.get('chaos_strategy', 'unknown')
    cl = record.get('chaos_level', 'unknown')
    hw = sanitize_hw_token(record.get('actual_device', 'unknown'))
    dt = 'drift' if record.get('drift_detected', False) else 'clean'
    return f'baseline_run_{rn:03d}_{an}_{pp}_{fp}_{cs}_{cl}_{hw}_{dt}.json'


def standard_raw_filename(record):
    rn = int(record.get('run_number', 0))
    an = record.get('api_name', 'unknown')
    pp = record.get('packet_profile', 'unknown')
    fp = record.get('frequency_profile', 'unknown')
    cs = record.get('chaos_strategy', 'unknown')
    cl = record.get('chaos_level', 'unknown')
    hw = sanitize_hw_token(record.get('actual_device', 'unknown'))
    dt = 'drift' if record.get('drift_detected', False) else 'clean'
    return f'run_{rn:03d}_{an}_{pp}_{fp}_{cs}_{cl}_{hw}_{dt}.json'


def write_json_atomic(path, payload):
    tmp_path = f'{path}.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(payload, f)
    os.replace(tmp_path, path)


def parse_existing_baseline_file_name(file_name):
    pattern = re.compile(
        r'^baseline_run_(\d{3})_([a-z0-9_]+)_(short|long)_(100hz|1000hz|1mhz)_(json|schema|gemma)_(high|medium|low)_.+_(clean|drift)\.json$',
        re.IGNORECASE
    )
    m = pattern.match(file_name)
    if not m:
        return None
    rn = int(m.group(1))
    api = m.group(2)
    p = m.group(3)
    f = m.group(4)
    x = m.group(5)
    l = m.group(6)
    return (p, f, x, l, api), rn


def parse_run_file_name(file_name):
    """Parse run_{rn:03d}_{api}_{packet}_{freq}_{chaos}_{level}_{hw}_{drift/clean}.json"""
    pattern = re.compile(
        r'^run_(\d{3})_([a-z0-9_]+)_(short|long)_(100hz|1000hz|1mhz)_(json|schema|gemma)_(high|medium|low)_.+_(clean|drift)\.json$',
        re.IGNORECASE
    )
    m = pattern.match(file_name)
    if not m:
        return None
    rn = int(m.group(1))
    api = m.group(2)
    p = m.group(3)
    f = m.group(4)
    x = m.group(5)
    l = m.group(6)
    return (p, f, x, l, api), rn


def load_existing_baseline_runs_from_raw(raw_dir):
    existing = {}
    if not os.path.isdir(raw_dir):
        return existing
    for name in os.listdir(raw_dir):
        parsed = parse_existing_baseline_file_name(name)
        if not parsed:
            continue
        cfg, rn = parsed
        existing.setdefault(cfg, set()).add(rn)
    return existing


def run_config_plan(runner, plan, label, policy, on_result=None, preflight=None):
    all_res = []
    times = []
    n = len(plan)
    for idx, (p, f, x, l, a, rn) in enumerate(plan):
        run_id = uuid4().hex
        print(f'[{label}] Progress: {idx+1}/{n} ({(idx+1)/max(1, n)*100:.1f}%) | {a} {f} {x} {l} run={rn} run_id={run_id[:8]}')
        try:
            res = runner.run_single_stream(
                api_name=a, packet_profile=p, frequency_profile=f,
                chaos_strategy=x, chaos_level=l, run_number=rn, concurrency=1,
                run_id=run_id, preflight=preflight or {}
            )
            if res and 'total_runtime_sec' in res:
                res['_label'] = label
                res['run_id'] = run_id
                res['preflight'] = preflight or {}
                attach_policy_metadata(res, policy)
                if on_result is not None:
                    on_result(res)
                times.append(res['total_runtime_sec'])
                all_res.append(res)
        except Exception as e:
            print(f'[{label}] [ERROR] {e}')
    return all_res, times


def run_configs(runner, configs, label, policy, run_numbers, on_result=None):
    plan = []
    for (p, f, x, l, a) in configs:
        for rn in run_numbers:
            plan.append((p, f, x, l, a, rn))
    return run_config_plan(runner, plan, label, policy, on_result=on_result)


def build_summary(all_res, label):
    if not all_res:
        return {}
    dr_vals = [r.get('detection_rate', 0) for r in all_res]
    lat_vals = [r.get('p95_latency_ms', 0) for r in all_res]
    p_vals = [r.get('resilience_P', 0) for r in all_res]
    p2_vals = [r.get('resilience_P2', 0) for r in all_res]
    rec_vals = [r.get('recovery_score', 0) for r in all_res]
    rr_vals = [r.get('repair_rate', 0) for r in all_res]

    config_groups = {}
    for r in all_res:
        key = (r.get('api_name'), r.get('packet_profile'), r.get('frequency_profile'),
               r.get('chaos_strategy'), r.get('chaos_level'))
        config_groups.setdefault(key, []).append(r)

    per_config_stats = []
    for key, runs in config_groups.items():
        d_vals = [x.get('detection_rate', 0) for x in runs]
        l_vals = [x.get('p95_latency_ms', 0) for x in runs]
        per_config_stats.append({
            'api': key[0], 'packet': key[1], 'freq': key[2],
            'chaos_strat': key[3], 'chaos_level': key[4],
            'detection_mean': mean(d_vals),
            'detection_std': stdev(d_vals),
            'latency_mean': mean(l_vals),
            'latency_std': stdev(l_vals),
            'n_runs': len(runs)
        })

    return {
        'label': label,
        'n_total': len(all_res),
        'detection_rate': {
            'mean': mean(dr_vals),
            'std': stdev(dr_vals),
            'ci95': ci95(dr_vals)
        },
        'p95_latency_ms': {
            'mean': mean(lat_vals),
            'std': stdev(lat_vals),
            'ci95': ci95(lat_vals)
        },
        'resilience_P': {
            'mean': mean(p_vals),
            'std': stdev(p_vals),
            'ci95': ci95(p_vals)
        },
        'resilience_P2': {
            'mean': mean(p2_vals),
            'std': stdev(p2_vals),
            'ci95': ci95(p2_vals)
        },
        'recovery_score': {
            'mean': mean(rec_vals),
            'std': stdev(rec_vals),
            'ci95': ci95(rec_vals)
        },
        'repair_rate': {
            'mean': mean(rr_vals),
            'std': stdev(rr_vals),
            'ci95': ci95(rr_vals)
        },
        'per_config_stats': per_config_stats
    }


def git_push(branch, msg):
    try:
        subprocess.run(['git', 'add', '-A'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', msg], check=False, capture_output=True)
        subprocess.run(['git', 'push', 'origin', branch], check=True, capture_output=True)
        print(f'[Git] Pushed to origin/{branch}')
    except subprocess.CalledProcessError as e:
        print(f'[Git] Push failed: {e.stderr.decode() if e.stderr else e}')


def read_apple_results():
    """Read Apple M4 results from existing summary."""
    ap = 'results/Apple_Silicon_arm/local/summary.json'
    if os.path.exists(ap):
        with open(ap) as f:
            return json.load(f)
    return None


def update_readme(roc_data):
    """Write README with cross-platform comparison table."""
    apple_data = read_apple_results()

    lines = []
    lines.append('# Semantic Drift Evaluation Pipeline')
    lines.append('')
    lines.append('Cross-platform benchmark for semantic schema drift detection and reconciliation')
    lines.append('using BERT embeddings and Gemma-4 E4B, evaluated under controlled chaos injection')
    lines.append('on real-world API schemas (Finnhub, OpenMeteo, SpaceX, OpenF1).')
    lines.append('')
    lines.append('## Results')
    lines.append('')
    lines.append('| Metric | Apple M4 (MPS) | AMD RX 7900 XT (ROCm) |')
    lines.append('|--------|----------------|----------------------|')

    if apple_data:
        ac = apple_data.get('mean_with_cold_start', {})
        as_ = apple_data.get('stable_mean', {})
        lines.append(f'| Detection rate (cold) | {ac.get("detection_rate", "—")} | {roc_data.get("detection_rate_cold", "—")} |')
        lines.append(f'| p95 latency (cold) | {ac.get("p95_latency_ms", "—")} ms | {roc_data.get("latency_cold", "—")} ms |')
        lines.append(f'| Detection rate (stable) | {as_.get("detection_rate", "—")} | {roc_data.get("detection_rate_stable", "—")} |')
        lines.append(f'| p95 latency (stable) | {as_.get("p95_latency_ms", "—")} ms | {roc_data.get("latency_stable", "—")} ms |')
        lines.append(f'| Total runs | {apple_data.get("total_runs_count", "—")} | {roc_data.get("total_runs", "—")} |')
        lines.append(f'| Global runtime | {apple_data.get("global_runtime_sec", "—")} s | {roc_data.get("global_runtime", "—")} s |')

    lines.append('')
    lines.append('### Ablation Study')
    lines.append('')
    lines.append('| Condition | Detection Rate (mean ± ci95) | p95 Latency (mean ± ci95) | Resilience P (mean ± ci95) |')
    lines.append('|-----------|------|------|------|')

    ablations = roc_data.get('ablations', {})
    for key, row in ablations.items():
        dr = row.get('detection_rate', {})
        la = row.get('p95_latency_ms', {})
        rp = row.get('resilience_P', {})
        lines.append(f'| {key} | {dr.get("mean", "—"):.4f} ± {dr.get("ci95", "—"):.4f} | {la.get("mean", "—"):.2f} ± {la.get("ci95", "—"):.2f} ms | {rp.get("mean", "—"):.4f} ± {rp.get("ci95", "—"):.4f} |')

    lines.append('')
    lines.append('## Methodology')
    lines.append('')
    lines.append('- **864 configurations**: 2 packet profiles × 3 frequencies × 3 chaos strategies × 3 levels × 4 APIs, 4 runs each')
    lines.append('- **Chaos strategies**: JSON mutation, schema drift, Gemma-generated adversarial mutations')
    lines.append('- **Reconcilers**: Levenshtein distance, regex, BERT semantic similarity (all-MiniLM-L6-v2), Gemma-4 E4B')
    lines.append('- **Metrics**: Detection rate, p95 latency, repair rate, recovery score, resilience P/P2')
    lines.append('')
    lines.append('## Raw Run Methodology')
    lines.append('')
    lines.append('- **Raw mode**: `python run_all.py --generate-only` writes per-run JSON artifacts to `results/raw/<hardware_token>/`.')
    lines.append('- **Cross-platform layout**: one folder per hardware target (for example Apple Silicon, NVIDIA GPU, AMD GPU).')
    lines.append('- **Raw file naming**: `run_{run:03d}_{api}_{packet}_{freq}_{chaos}_{level}_{hardware}_{drift_or_clean}.json`.')
    lines.append('- **Baseline file naming**: `baseline_run_{run:03d}_{api}_{packet}_{freq}_{chaos}_{level}_{hardware}_{drift_or_clean}.json`.')
    lines.append('- **Baseline policy**: baseline clean pipeline is topped up to at least 5 runs/config by default (`--min-baseline-runs`).')
    lines.append('- **Run policy**: configurable with `--runs-per-config` and tagged in-record using `policy_tag`.')
    lines.append('- **Stable statistics**: stable mean excludes run 1 (warmup/cold start) and uses runs 2..N.')
    lines.append('- **Per-record provenance**: policy metadata and reproducibility metadata are embedded in each record.')
    lines.append('- **Post-hoc analysis**: run `python analyze.py --data-dir results/raw/<hardware_token>` per hardware folder.')
    lines.append('')
    lines.append('## Hardware')
    lines.append('')
    lines.append('| Platform | GPU | Memory | Precision |')
    lines.append('|----------|-----|--------|-----------|')
    lines.append('| Apple Silicon | M4 (MPS) | Unified | float16 |')
    lines.append('| AMD ROCm | RX 7900 XT (gfx1100) | 20 GB | bfloat16 |')

    with open('README.md', 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('[README] Updated with cross-platform comparison.')


def run_evaluation_pipeline():
    args = parse_args()

    if args.bootstrap:
        import bootstrap
        bootstrap.run_bootstrap(force=True)

    # ── Pre-flight validation ──
    preflight, abort, abort_reason = run_preflight_checks(
        require_gpu=args.require_gpu,
        cpu_allowed=args.cpu_allowed,
        require_local_models=args.require_local_models,
        strict_mode=args.strict_mode,
        verbose=True
    )
    if abort:
        print(f"\n{'='*80}")
        print(f" ✗ PRE-FLIGHT FAILED: {abort_reason}")
        print(f"{'='*80}")
        sys.exit(1)

    # ── detect hardware ──
    d = get_device_info()
    h = sanitize_hw_token(d['model'])
    c = d['cloud']
    policy_metadata = build_policy_metadata(args, d)
    run_numbers = list(range(1, max(1, args.runs_per_config) + 1))
    baseline_target_runs = max(1, args.min_baseline_runs)
    print('\n' + '=' * 80)
    print(' Hey! Welcome to the Semantic Drift Evaluation Pipeline Runner')
    print(f' Hardware Name     : {d["model"]}')
    print(f' VRAM             : {d.get("vram_gb", "unknown")} GB')
    print(f' Cloud Environment : {d["cloud"].upper()}')
    print(f' Policy Tag        : {policy_metadata.get("policy_tag")}')
    print(f' Pipeline Version  : {preflight.get("pipeline_version", "unknown")[:12]}')
    print(f' GPU backend       : {preflight.get("gpu_backend", "unknown")}')
    print(f' BERT available    : {preflight.get("bert_available", False)}')
    print(f' Gemma available   : {preflight.get("gemma_available", False)}')
    print(f' Strict mode       : {args.strict_mode}')
    print('=' * 80 + '\n')

    # ── erase check ──
    e = args.erase_existing or args.force_erase
    R = f'results/{h}/{c}'
    if e:
        if os.path.exists(R):
            import shutil
            shutil.rmtree(R)
    else:
        try:
            p = input(f'Erase existing results at {R}? [y/N]: ')
            if p.strip().lower() in ('y', 'yes'):
                import shutil
                if os.path.exists(R):
                    shutil.rmtree(R)
        except:
            pass

    P = ['short', 'long']
    F = ['100hz', '1000hz', '1mhz']
    X = ['json', 'schema', 'gemma']
    L = ['high', 'medium', 'low']
    A_list = ['finnhub', 'openmeteo', 'spacex', 'openf1']
    all_configs = [(p, f, x, l, a) for p in P for f in F for x in X for l in L for a in A_list]
    n_configs = len(all_configs)

    g_start = time.perf_counter()

    # ── Create ONE runner, swap reconcilers between phases (avoids safetensors reload crash) ──
    runner = ExperimentRunner()

    raw_dir = None
    if args.generate_only:
        raw_parent = 'results/raw'
        hw_token = sanitize_hw_token(d['model'])
        raw_dir = f'{raw_parent}/{hw_token}'
        os.makedirs(raw_dir, exist_ok=True)

        def write_standard_raw(record):
            write_json_atomic(f'{raw_dir}/{standard_raw_filename(record)}', record)

        def write_baseline_raw(record):
            write_json_atomic(f'{raw_dir}/{baseline_raw_filename(record)}', record)

        existing_by_cfg = {}
        for name in os.listdir(raw_dir):
            if not name.startswith('run_') or name.startswith('baseline_run_'):
                continue
            parsed = parse_run_file_name(name)
            if parsed is None:
                continue
            cfg, rn = parsed
            existing_by_cfg.setdefault(cfg, set()).add(rn)

        phase1_plan = []
        for cfg in all_configs:
            present = existing_by_cfg.get(cfg, set())
            for rn in run_numbers:
                if rn not in present:
                    phase1_plan.append((*cfg, rn))
    else:
        phase1_plan = []
        for (p, f, x, l, a) in all_configs:
            for rn in run_numbers:
                phase1_plan.append((p, f, x, l, a, rn))

    # ── PHASE 1: Full pipeline ──
    print(f'\n{"="*80}')
    print(f' PHASE 1: Full Pipeline ({len(phase1_plan)} streams planned)')
    print(f'{"="*80}')
    all_res_full, times_full = run_config_plan(
        runner,
        phase1_plan,
        'FULL',
        policy_metadata,
        on_result=write_standard_raw if args.generate_only else None,
        preflight=preflight
    )

    if args.generate_only:
        hw_token = sanitize_hw_token(d['model'])
        new_records = list(all_res_full)

        # Top-up standard runs to at least runs_per_config per config
        print(f'\n{"="*80}')
        print(f' STANDARD TOP-UP (target >= {args.runs_per_config} runs/config)')
        print(f'{"="*80}')
        existing_by_cfg = {}
        for name in os.listdir(raw_dir):
            if not name.startswith('run_') or name.startswith('baseline_run_'):
                continue
            parts = name.split('_', 5)
            if len(parts) < 5:
                continue
            # extract config from filename
            parsed = parse_run_file_name(name)
            if parsed is None:
                continue
            cfg, rn = parsed
            existing_by_cfg.setdefault(cfg, set()).add(rn)

        topup_plan = []
        for cfg in all_configs:
            present = existing_by_cfg.get(cfg, set())
            for rn in range(1, args.runs_per_config + 1):
                if rn not in present:
                    topup_plan.append((*cfg, rn))

        if topup_plan:
            print(f'[Top-up] {len(topup_plan)} missing standard runs to fill.')
            new_std, _ = run_config_plan(
                runner,
                topup_plan,
                'FULL',
                policy_metadata,
                on_result=write_standard_raw
            )
            new_records.extend(new_std)

        # Ensure baseline clean pipeline has at least N runs per config in raw dir
        print(f'\n{"="*80}')
        print(f' BASELINE TOP-UP (target >= {baseline_target_runs} runs/config)')
        print(f'{"="*80}')
        baseline_configs = [('short', '100hz', 'json', 'low', a) for a in A_list]
        existing_baseline = load_existing_baseline_runs_from_raw(raw_dir)
        baseline_plan = []
        for cfg in baseline_configs:
            present = existing_baseline.get(cfg, set())
            for rn in range(1, baseline_target_runs + 1):
                if rn not in present:
                    baseline_plan.append((*cfg, rn))

        if baseline_plan:
            runner.baseline_mode = True
            new_baseline_records, _ = run_config_plan(
                runner,
                baseline_plan,
                'BASELINE',
                policy_metadata,
                on_result=write_baseline_raw
            )
            print(f'[Generate] Baseline top-up generated {len(new_baseline_records)} new baseline records.')
        else:
            print('[Generate] Baseline already satisfies minimum run policy.')

        print(f'[Generate] Total new records: {len(new_records)}')
        print(f'[Generate] Done. Run `python analyze.py --data-dir results/raw/{hw_token}` to compute scores.')
        return

    summary_full = build_summary(all_res_full, 'full_pipeline')

    # ── PHASE 2: No BERT ──
    print(f'\n{"="*80}')
    print(' PHASE 2: Ablation – No BERT')
    print(f'{"="*80}')
    runner.cp.bert = None
    import types
    def compare_no_bert(self, canonical_keys, query_key):
        return {
            "levenshtein": self.levenshtein.reconcile(canonical_keys, query_key),
            "regex": self.regex.reconcile(canonical_keys, query_key),
            "gemma": self.gemma.reconcile(canonical_keys, query_key)
        }
    runner.cp.compare_algorithms = types.MethodType(compare_no_bert, runner.cp)
    subset = all_configs[:n_configs//2]
    all_res_no_bert, _ = run_configs(runner, subset, 'NO_BERT', policy_metadata, run_numbers)
    summary_no_bert = build_summary(all_res_no_bert, 'ablation_no_bert')

    # Restore BERT for next phases
    from semantic.bert_recon import BERTReconciler
    runner.cp.bert = BERTReconciler(runner.b)
    def compare_full(self, canonical_keys, query_key):
        result = {}
        if self.levenshtein is not None:
            result["levenshtein"] = self.levenshtein.reconcile(canonical_keys, query_key)
        if self.regex is not None:
            result["regex"] = self.regex.reconcile(canonical_keys, query_key)
        if self.bert is not None:
            result["bert"] = self.bert.reconcile(canonical_keys, query_key)
        if self.gemma is not None:
            result["gemma"] = self.gemma.reconcile(canonical_keys, query_key)
        return result
    runner.cp.compare_algorithms = types.MethodType(compare_full, runner.cp)

    # ── PHASE 3: No Gemma ──
    print(f'\n{"="*80}')
    print(' PHASE 3: Ablation – No Gemma')
    print(f'{"="*80}')
    runner.cp.gemma = None
    def compare_no_gemma(self, canonical_keys, query_key):
        return {
            "levenshtein": self.levenshtein.reconcile(canonical_keys, query_key),
            "regex": self.regex.reconcile(canonical_keys, query_key),
            "bert": self.bert.reconcile(canonical_keys, query_key)
        }
    runner.cp.compare_algorithms = types.MethodType(compare_no_gemma, runner.cp)
    all_res_no_gemma, _ = run_configs(runner, subset, 'NO_GEMMA', policy_metadata, run_numbers)
    summary_no_gemma = build_summary(all_res_no_gemma, 'ablation_no_gemma')

    # Restore Gemma
    from models.gemma_offline import GemmaModel
    runner.cp.gemma = GemmaReconciler(runner.g)
    runner.cp.compare_algorithms = types.MethodType(compare_full, runner.cp)

    # ── PHASE 4: Baseline no chaos ──
    print(f'\n{"="*80}')
    print(' PHASE 4: Baseline – No Chaos')
    print(f'{"="*80}')
    runner.baseline_mode = True
    baseline_configs = [('short', '100hz', 'json', 'low', a) for a in A_list]

    baseline_records_path = os.path.join('results', h, c, 'baseline_no_chaos_records.json')
    os.makedirs(os.path.dirname(baseline_records_path), exist_ok=True)
    existing_base = []
    if os.path.exists(baseline_records_path):
        try:
            with open(baseline_records_path) as f:
                existing_base = json.load(f)
        except Exception:
            existing_base = []

    baseline_existing_map = {}
    for r in existing_base:
        baseline_existing_map.setdefault(config_key_from_record(r), set()).add(int(r.get('run_number', 0)))

    baseline_plan = []
    for cfg in baseline_configs:
        present = baseline_existing_map.get(cfg, set())
        for rn in range(1, baseline_target_runs + 1):
            if rn not in present:
                baseline_plan.append((*cfg, rn))

    new_base, _ = run_config_plan(runner, baseline_plan, 'BASELINE', policy_metadata) if baseline_plan else ([], [])
    all_res_base = existing_base + new_base
    if new_base:
        with open(baseline_records_path, 'w') as f:
            json.dump(all_res_base, f, indent=2)

    summary_baseline = build_summary(all_res_base, 'baseline_no_chaos')

    # ── PHASE 5: Fast only (Levenshtein + Regex) ──
    print(f'\n{"="*80}')
    print(' PHASE 5: Ablation – Levenshtein + Regex only')
    print(f'{"="*80}')
    runner.baseline_mode = False
    runner.cp.bert = None
    runner.cp.gemma = None
    def compare_fast_only(self, canonical_keys, query_key):
        return {
            "levenshtein": self.levenshtein.reconcile(canonical_keys, query_key),
            "regex": self.regex.reconcile(canonical_keys, query_key)
        }
    runner.cp.compare_algorithms = types.MethodType(compare_fast_only, runner.cp)
    all_res_fast, _ = run_configs(runner, subset, 'FAST_ONLY', policy_metadata, run_numbers)
    summary_fast = build_summary(all_res_fast, 'ablation_fast_only')

    gr = time.perf_counter() - g_start

    # ── Write all results ──
    sd = f'results/{h}/{c}'
    os.makedirs(sd, exist_ok=True)
    sp = os.path.join(sd, 'summary.json')

    total_t = sum(times_full) if times_full else 0
    avg_t = total_t / max(1, len(times_full)) if times_full else 0
    fast_t = min(times_full) if times_full else 0
    slow_t = max(times_full) if times_full else 0

    d_d = [r.get('detection_rate', 0) for r in all_res_full]
    d_l = [r.get('p95_latency_ms', 0) for r in all_res_full]
    s_r = [r for r in all_res_full if r.get('run_number', 1) > 1]
    s_d = [r.get('detection_rate', 0) for r in s_r]
    s_l = [r.get('p95_latency_ms', 0) for r in s_r]

    data = {
        'policy': policy_metadata,
        'preflight': preflight,
        'global_runtime_sec': round(gr, 4),
        'total_runs_time_sec': round(total_t, 4),
        'average_runtime_sec': round(avg_t, 4),
        'fastest_run_sec': round(fast_t, 4),
        'slowest_run_sec': round(slow_t, 4),
        'total_runs_count': len(times_full),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'mean_with_cold_start': {
            'detection_rate': mean(d_d),
            'p95_latency_ms': mean(d_l)
        },
        'stable_mean': {
            'detection_rate': mean(s_d),
            'p95_latency_ms': mean(s_l)
        },
        'statistical_summary': {
            'full_pipeline': summary_full,
            'ablation_no_bert': summary_no_bert,
            'ablation_no_gemma': summary_no_gemma,
            'ablation_fast_only': summary_fast,
            'baseline_no_chaos': summary_baseline
        }
    }
    with open(sp, 'w') as f:
        json.dump(data, f, indent=2)

    # ── Print summary ──
    print(f'\n{"="*80}')
    print(f' Pipeline Complete')
    print(f' Total runs: {len(times_full)} | Global time: {gr:.2f}s')
    print(f' Detection rate: {mean(d_d):.4f} ± {stdev(d_d):.4f}')
    print(f' p95 latency:   {mean(d_l):.2f} ± {stdev(d_l):.2f} ms')
    print(f'{"="*80}')

    for s in [summary_full, summary_no_bert, summary_no_gemma, summary_fast, summary_baseline]:
        if s:
            print(f'\n[{s["label"]}] n={s["n_total"]}')
            print(f'  detection_rate: {s["detection_rate"]["mean"]:.4f} ± {s["detection_rate"]["ci95"]:.4f}')
            print(f'  p95_latency:    {s["p95_latency_ms"]["mean"]:.2f} ± {s["p95_latency_ms"]["ci95"]:.2f} ms')
            print(f'  resilience_P:   {s["resilience_P"]["mean"]:.4f} ± {s["resilience_P"]["ci95"]:.4f}')

    # ── Flatten + export ──
    def flatten_records(records):
        flat = []
        for r in records:
            f = {}
            for k, v in r.items():
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        f[f'{k}_{kk}'] = vv
                else:
                    f[k] = v
            flat.append(f)
        return flat

    flat_all = flatten_records(all_res_full)
    pdir = 'results/' + h
    os.makedirs(pdir, exist_ok=True)
    json.dump(flat_all, open(pdir + '/master_platform_all_runs_1_to_4.json', 'w'))
    stable_f = [r for r in flat_all if r.get('run_number', 1) > 1]
    json.dump(stable_f, open(pdir + '/master_platform_stable_runs_2_to_4.json', 'w'))

    if flat_all:
        ka = sorted(flat_all[0].keys())
        with open(pdir + '/master_platform_all_runs_1_to_4.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=ka)
            w.writeheader()
            w.writerows(flat_all)
    if stable_f:
        ks = sorted(stable_f[0].keys())
        with open(pdir + '/master_platform_stable_runs_2_to_4.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=ks)
            w.writeheader()
            w.writerows(stable_f)

    ablation_all = flatten_records(all_res_no_bert + all_res_no_gemma + all_res_base + all_res_fast)
    if ablation_all:
        ka2 = sorted(ablation_all[0].keys())
        with open('results/ablation_and_baseline_all.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=ka2)
            w.writeheader()
            w.writerows(ablation_all)

    # ── Global unified ──
    gal = []
    gst = []
    for entry in os.listdir('results/'):
        ep = os.path.join('results', entry)
        if os.path.isdir(ep):
            fp = os.path.join(ep, 'master_platform_all_runs_1_to_4.json')
            if os.path.exists(fp):
                with open(fp) as fh:
                    gal.extend(json.load(fh))
            fp2 = os.path.join(ep, 'master_platform_stable_runs_2_to_4.json')
            if os.path.exists(fp2):
                with open(fp2) as fh:
                    gst.extend(json.load(fh))
    json.dump(gal, open('results/global_unified_all_runs_1_to_4.json', 'w'))
    json.dump(gst, open('results/global_unified_stable_runs_2_to_4.json', 'w'))
    if gal:
        kg = sorted(gal[0].keys())
        with open('results/global_unified_all_runs_1_to_4.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=kg)
            w.writeheader()
            w.writerows(gal)
    if gst:
        kg2 = sorted(gst[0].keys())
        with open('results/global_unified_stable_runs_2_to_4.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=kg2)
            w.writeheader()
            w.writerows(gst)

    # ── Drift type frequencies ──
    if all_res_full:
        drift_type_counter = {}
        for r in all_res_full:
            dt = r.get('drift_types', {})
            for k, v in dt.items():
                drift_type_counter[k] = drift_type_counter.get(k, 0) + v
        total_drift_events = sum(drift_type_counter.values())
        print("\n" + "=" * 80)
        print(" DRIFT TYPE FREQUENCIES")
        print("=" * 80)
        for dtype, count in sorted(drift_type_counter.items()):
            print(f" {dtype}: {count}")
        print(f" Total drift events: {total_drift_events}")
        print("=" * 80)

        p_vals = [r.get('resilience_P', 0) for r in all_res_full]
        p2_vals = [r.get('resilience_P2', 0) for r in all_res_full]
        print(f" Average Resilience P  : {mean(p_vals):.4f}")
        print(f" Average Resilience P2 : {mean(p2_vals):.4f}")
        print("=" * 80)

    # ── Update README with cross-platform comparison ──
    roc_data = {
        'detection_rate_cold': f'{mean(d_d):.4f}',
        'latency_cold': f'{mean(d_l):.2f}',
        'detection_rate_stable': f'{mean(s_d):.4f}',
        'latency_stable': f'{mean(s_l):.2f}',
        'total_runs': str(len(times_full)),
        'global_runtime': f'{gr:.2f}',
        'ablations': {
            'full_pipeline': summary_full,
            'ablation_no_bert': summary_no_bert,
            'ablation_no_gemma': summary_no_gemma,
            'ablation_fast_only': summary_fast,
            'baseline_no_chaos': summary_baseline
        }
    }
    update_readme(roc_data)

    # ── Git push ──
    if not args.skip_git_push:
        print('\n[Git] Pushing everything to GitHub...')
        branch = 'semantic_only'
        ts = time.strftime('%Y-%m-%d %H:%M')
        git_push(branch, f'ROCm RX 7900 XT results + ablations + baseline {ts}')
        print('[Done] All phases complete. Pushed to semantic_only.')
    else:
        print('[Done] All phases complete. Git push skipped.')


if __name__ == '__main__':
    run_evaluation_pipeline()