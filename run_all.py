import os
import sys
import json
import time
import csv
import math
import subprocess
from models.device_selector import get_device_info
from models.bert_model import BERTModel
from semantic.gemma_recon import GemmaReconciler
from tests.run_experiments import ExperimentRunner


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

def run_configs(runner, configs, label):
    all_res = []
    times = []
    n = len(configs)
    for idx, (p, f, x, l, a) in enumerate(configs):
        print(f'[{label}] Progress: {idx+1}/{n} ({(idx+1)/n*100:.1f}%) | {a} {f} {x} {l}')
        for rn in [1, 2, 3, 4]:
            try:
                res = runner.run_single_stream(
                    api_name=a, packet_profile=p, frequency_profile=f,
                    chaos_strategy=x, chaos_level=l, run_number=rn, concurrency=1
                )
                if res and 'total_runtime_sec' in res:
                    res['_label'] = label
                    times.append(res['total_runtime_sec'])
                    all_res.append(res)
            except Exception as e:
                print(f'[{label}] [ERROR] {e}')
    return all_res, times


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
    if '--bootstrap' in sys.argv:
        import bootstrap
        bootstrap.run_bootstrap(force=True)

    # ── detect hardware ──
    d = get_device_info()
    h = d['model'].replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
    c = d['cloud']
    print('\n' + '=' * 80)
    print(' Hey! Welcome to the Semantic Drift Evaluation Pipeline Runner')
    print(f' Hardware Platform : {d["device"].upper()}')
    print(f' Hardware Model    : {d["model"]}')
    print(f' Cloud Environment : {d["cloud"].upper()}')
    print('=' * 80 + '\n')

    # ── erase check ──
    e = '--erase-existing' in sys.argv or '--force-erase' in sys.argv
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

    # ── PHASE 1: Full pipeline ──
    print(f'\n{"="*80}')
    print(f' PHASE 1: Full Pipeline ({n_configs} configs x 4 runs = {n_configs*4} streams)')
    print(f'{"="*80}')
    all_res_full, times_full = run_configs(runner, all_configs, 'FULL')
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
    all_res_no_bert, _ = run_configs(runner, subset, 'NO_BERT')
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
    all_res_no_gemma, _ = run_configs(runner, subset, 'NO_GEMMA')
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
    all_res_base, _ = run_configs(runner, baseline_configs, 'BASELINE')
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
    all_res_fast, _ = run_configs(runner, subset, 'FAST_ONLY')
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
    print('\n[Git] Pushing everything to GitHub...')
    branch = 'semantic_only'
    ts = time.strftime('%Y-%m-%d %H:%M')
    git_push(branch, f'ROCm RX 7900 XT results + ablations + baseline {ts}')
    print('[Done] All phases complete. Pushed to semantic_only.')


if __name__ == '__main__':
    run_evaluation_pipeline()