#!/usr/bin/env python3
"""
analyze.py — Post-hoc analysis of raw pipeline JSONs.

Read raw per-run JSON files (saved by `run_all.py --generate-only`),
compute resilience scores with any formula weights, produce stats,
update README, and push to GitHub.

Usage:
    python analyze.py [--weights 0.35,0.25,0.20,0.20] [--p2-weights 0.30,0.30,0.25,0.15]
                      [--baseline-p95 10.0] [--push] [--no-readme]
"""

import os
import sys
import json
import time
import csv
import math
import glob
import subprocess
import argparse


# ── helpers ─────────────────────────────────────────────────────────────

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


# ── resilience scoring (configurable) ────────────────────────────────────

class ResilienceFormula:
    """Calculate resilience scores with configurable weights."""

    def __init__(self, wT=0.35, wD=0.25, wR=0.20, wL=0.20,
                 wT2=0.30, wD2=0.30, wR2=0.25, wL2=0.15,
                 baseline_p95_ms=10.0):
        self.wT = wT; self.wD = wD; self.wR = wR; self.wL = wL
        self.wT2 = wT2; self.wD2 = wD2; self.wR2 = wR2; self.wL2 = wL2
        self.baseline_p95_ms = baseline_p95_ms

    def score(self, throughput_pps, target_hz, detection_rate,
              recovery_score, p95_latency_ms):
        T = min(1.0, max(0.0, throughput_pps / max(1.0, target_hz)))
        D = min(1.0, max(0.0, float(detection_rate)))
        R = min(1.0, max(0.0, float(recovery_score)))
        L = min(1.0, max(0.0, self.baseline_p95_ms / max(1e-6, float(p95_latency_ms))))
        P = self.wT*T + self.wD*D + self.wR*R + self.wL*L
        P2 = self.wT2*T + self.wD2*D + self.wR2*R + self.wL2*L
        return P, P2, T, D, R, L


# ── stats builder ────────────────────────────────────────────────────────

def build_statistical_summary(all_res, label):
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

    per_config = []
    for key, runs in config_groups.items():
        d_vals = [x.get('detection_rate', 0) for x in runs]
        l_vals = [x.get('p95_latency_ms', 0) for x in runs]
        per_config.append({
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
        'detection_rate': {'mean': mean(dr_vals), 'std': stdev(dr_vals), 'ci95': ci95(dr_vals)},
        'p95_latency_ms': {'mean': mean(lat_vals), 'std': stdev(lat_vals), 'ci95': ci95(lat_vals)},
        'resilience_P':   {'mean': mean(p_vals), 'std': stdev(p_vals), 'ci95': ci95(p_vals)},
        'resilience_P2':  {'mean': mean(p2_vals), 'std': stdev(p2_vals), 'ci95': ci95(p2_vals)},
        'recovery_score': {'mean': mean(rec_vals), 'std': stdev(rec_vals), 'ci95': ci95(rec_vals)},
        'repair_rate':    {'mean': mean(rr_vals), 'std': stdev(rr_vals), 'ci95': ci95(rr_vals)},
        'per_config_stats': per_config
    }


# ── README writer ────────────────────────────────────────────────────────

def read_apple_results():
    ap = 'results/Apple_Silicon_arm/local/summary.json'
    if os.path.exists(ap):
        with open(ap) as f:
            return json.load(f)
    return None

def update_readme(roc_data):
    apple_data = read_apple_results()
    lines = [
        '# Semantic Drift Evaluation Pipeline',
        '',
        'Cross-platform benchmark for semantic schema drift detection and reconciliation',
        'using BERT embeddings and Gemma-4 E4B, evaluated under controlled chaos injection',
        'on real-world API schemas (Finnhub, OpenMeteo, SpaceX, OpenF1).',
        '',
        '## Results',
        '',
        '| Metric | Apple M4 (MPS) | AMD RX 7900 XT (ROCm) |',
        '|--------|----------------|----------------------|',
    ]
    if apple_data:
        ac = apple_data.get('mean_with_cold_start', {})
        as_ = apple_data.get('stable_mean', {})
        lines.append(f'| Detection rate (cold) | {ac.get("detection_rate", "—")} | {roc_data.get("detection_rate_cold", "—")} |')
        lines.append(f'| p95 latency (cold) | {ac.get("p95_latency_ms", "—")} ms | {roc_data.get("latency_cold", "—")} ms |')
        lines.append(f'| Detection rate (stable) | {as_.get("detection_rate", "—")} | {roc_data.get("detection_rate_stable", "—")} |')
        lines.append(f'| p95 latency (stable) | {as_.get("p95_latency_ms", "—")} ms | {roc_data.get("latency_stable", "—")} ms |')
        lines.append(f'| Total runs | {apple_data.get("total_runs_count", "—")} | {roc_data.get("total_runs", "—")} |')
        lines.append(f'| Global runtime | {apple_data.get("global_runtime_sec", "—")} s | {roc_data.get("global_runtime", "—")} s |')

    lines += [
        '',
        '### Ablation Study',
        '',
        '| Condition | Detection Rate (mean ± ci95) | p95 Latency (mean ± ci95) | Resilience P (mean ± ci95) |',
        '|-----------|------|------|------|',
    ]
    for key, row in roc_data.get('ablations', {}).items():
        dr = row.get('detection_rate', {})
        la = row.get('p95_latency_ms', {})
        rp = row.get('resilience_P', {})
        lines.append(f'| {key} | {dr.get("mean", 0):.4f} ± {dr.get("ci95", 0):.4f} | {la.get("mean", 0):.2f} ± {la.get("ci95", 0):.2f} ms | {rp.get("mean", 0):.4f} ± {rp.get("ci95", 0):.4f} |')

    lines += [
        '',
        '## Methodology',
        '',
        '- **144 configurations / 720 total runs**: 2 packet profiles × 2 frequencies × 3 chaos strategies × 3 levels × 4 APIs, 5 runs each',
        '- **Chaos strategies**: JSON mutation, schema drift, Gemma-generated adversarial mutations',
        '- **Reconcilers**: Levenshtein distance, regex, BERT semantic similarity (all-MiniLM-L6-v2), Gemma-4 E4B',
        '- **Metrics**: Detection rate, p95 latency, repair rate, recovery score, resilience P/P2',
        '',
        '## Hardware',
        '',
        '| Platform | GPU | Memory | Precision |',
        '|----------|-----|--------|-----------|',
        '| Apple Silicon | M4 (MPS) | Unified | float16 |',
        '| AMD ROCm | RX 7900 XT (gfx1100) | 20 GB | bfloat16 |',
    ]
    with open('README.md', 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('[README] Updated with cross-platform comparison.')


# ── git push ─────────────────────────────────────────────────────────────

def git_push(branch, msg):
    try:
        subprocess.run(['git', 'add', '-A'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', msg], check=False, capture_output=True)
        subprocess.run(['git', 'push', 'origin', branch], check=True, capture_output=True)
        print(f'[Git] Pushed to origin/{branch}')
    except subprocess.CalledProcessError as e:
        print(f'[Git] Push failed: {e.stderr.decode() if e.stderr else e}')


# ── main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Analyze raw pipeline JSONs')
    parser.add_argument('--weights', default='0.35,0.25,0.20,0.20',
                        help='P weights: wT,wD,wR,wL')
    parser.add_argument('--p2-weights', default='0.30,0.30,0.25,0.15',
                        help='P2 weights: wT,wD,wR,wL')
    parser.add_argument('--baseline-p95', type=float, default=10.0,
                        help='Baseline p95 latency in ms')
    parser.add_argument('--push', action='store_true',
                        help='Push results to GitHub')
    parser.add_argument('--no-readme', action='store_true',
                        help='Skip README update')
    parser.add_argument('--data-dir', default='results/raw',
                        help='Directory with raw JSON files')
    args = parser.parse_args()

    w = [float(x) for x in args.weights.split(',')]
    w2 = [float(x) for x in args.p2_weights.split(',')]
    formula = ResilienceFormula(w[0], w[1], w[2], w[3],
                                w2[0], w2[1], w2[2], w2[3],
                                args.baseline_p95)

    print(f'Resilience formula P:  T×{w[0]} + D×{w[1]} + R×{w[2]} + L×{w[3]}')
    print(f'Resilience formula P2: T×{w2[0]} + D×{w2[1]} + R×{w2[2]} + L×{w2[3]}')
    print(f'Reading raw data from {args.data_dir}/ ...')

    # ── load raw records ─────────────────────────────────────────────────
    raw_files = sorted(glob.glob(os.path.join(args.data_dir, 'run_*.json')))
    if not raw_files:
        print(f'No raw JSON files found in {args.data_dir}/')
        sys.exit(1)

    all_records = []
    for fp in raw_files:
        with open(fp) as f:
            r = json.load(f)
            all_records.append(r)

    print(f'Loaded {len(all_records)} raw records.')

    # ── compute resilience scores for every record ───────────────────────
    for r in all_records:
        P, P2, Tn, Dn, Rn, Ln = formula.score(
            throughput_pps=r.get('throughput_pps', 0),
            target_hz=r.get('target_hz', 100),
            detection_rate=r.get('drift_detected', False),
            recovery_score=r.get('recovery_score', 0),
            p95_latency_ms=r.get('p95_latency_ms', 0),
        )
        r['resilience_P'] = P
        r['resilience_P2'] = P2
        r['detection_rate'] = 1.0 if r.get('drift_detected', False) else 0.0

    # ── group by _label ──────────────────────────────────────────────────
    groups = {}
    for r in all_records:
        label = r.get('_label', 'unknown')
        groups.setdefault(label, []).append(r)

    summaries = {}
    for label, recs in groups.items():
        summaries[label] = build_statistical_summary(recs, label)

    # ── pull out full_pipeline stats ─────────────────────────────────────
    full = summaries.get('full_pipeline', {})
    d_d = [r.get('detection_rate', 0) for r in groups.get('full_pipeline', [])]
    d_l = [r.get('p95_latency_ms', 0) for r in groups.get('full_pipeline', [])]
    tims = [r.get('total_runtime_sec', 0) for r in groups.get('full_pipeline', [])]
    s_r = [r for r in groups.get('full_pipeline', []) if r.get('run_number', 1) > 1]
    s_d = [r.get('detection_rate', 0) for r in s_r]
    s_l = [r.get('p95_latency_ms', 0) for r in s_r]

    # ── print summary ────────────────────────────────────────────────────
    print(f'\n{"="*80}')
    print(f' Total records: {len(all_records)}')
    print(f' Detection rate: {mean(d_d):.4f} ± {stdev(d_d):.4f}')
    print(f' p95 latency:   {mean(d_l):.2f} ± {stdev(d_l):.2f} ms')
    print(f'{"="*80}')

    for label, s in sorted(summaries.items()):
        if s:
            print(f'\n[{label}] n={s["n_total"]}')
            print(f'  detection_rate: {s["detection_rate"]["mean"]:.4f} ± {s["detection_rate"]["ci95"]:.4f}')
            print(f'  p95_latency:    {s["p95_latency_ms"]["mean"]:.2f} ± {s["p95_latency_ms"]["ci95"]:.2f} ms')
            print(f'  resilience_P:   {s["resilience_P"]["mean"]:.4f} ± {s["resilience_P"]["ci95"]:.4f}')
            print(f'  resilience_P2:  {s["resilience_P2"]["mean"]:.4f} ± {s["resilience_P2"]["ci95"]:.4f}')

    # ── build ROC data dict ──────────────────────────────────────────────
    roc_data = {
        'detection_rate_cold': f'{mean(d_d):.4f}',
        'latency_cold': f'{mean(d_l):.2f}',
        'detection_rate_stable': f'{mean(s_d):.4f}',
        'latency_stable': f'{mean(s_l):.2f}',
        'total_runs': str(len(tims)),
        'global_runtime': f'{sum(tims):.2f}',
        'ablations': summaries,
    }

    # ── write summary.json ───────────────────────────────────────────────
    # Figure out hardware name from a record
    hw = 'unknown'
    for r in all_records:
        hw = r.get('actual_device', r.get('device_hardware', 'unknown'))
        break
    cloud = 'local'
    for r in all_records:
        cloud = r.get('device_cloud', 'local')
        break

    sd = f'results/{hw}/{cloud}'
    os.makedirs(sd, exist_ok=True)
    summary_data = {
        'global_runtime_sec': round(sum(tims), 4),
        'total_runs_time_sec': round(sum(tims), 4),
        'average_runtime_sec': round(mean(tims), 4),
        'fastest_run_sec': round(min(tims), 4) if tims else 0,
        'slowest_run_sec': round(max(tims), 4) if tims else 0,
        'total_runs_count': len(tims),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'mean_with_cold_start': {'detection_rate': mean(d_d), 'p95_latency_ms': mean(d_l)},
        'stable_mean': {'detection_rate': mean(s_d), 'p95_latency_ms': mean(s_l)},
        'statistical_summary': summaries,
        'resilience_formula': {
            'P': {'wT': w[0], 'wD': w[1], 'wR': w[2], 'wL': w[3]},
            'P2': {'wT': w2[0], 'wD': w2[1], 'wR': w2[2], 'wL': w2[3]},
            'baseline_p95_ms': args.baseline_p95,
        },
    }
    with open(os.path.join(sd, 'summary.json'), 'w') as f:
        json.dump(summary_data, f, indent=2)
    print(f'\n[Summary] Written to {sd}/summary.json')

    # ── flatten CSV export ───────────────────────────────────────────────
    flat = []
    for r in all_records:
        f = {}
        for k, v in r.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    f[f'{k}_{kk}'] = vv
            else:
                f[k] = v
        flat.append(f)

    pdir = f'results/{hw}'
    os.makedirs(pdir, exist_ok=True)
    json.dump(flat, open(f'{pdir}/master_platform_all_runs_1_to_4.json', 'w'))
    stable_f = [r for r in flat if r.get('run_number', 1) > 1]
    json.dump(stable_f, open(f'{pdir}/master_platform_stable_runs_2_to_4.json', 'w'))
    if flat:
        ka = sorted(flat[0].keys())
        with open(f'{pdir}/master_platform_all_runs_1_to_4.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=ka)
            w.writeheader()
            w.writerows(flat)
    if stable_f:
        ks = sorted(stable_f[0].keys())
        with open(f'{pdir}/master_platform_stable_runs_2_to_4.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=ks)
            w.writeheader()
            w.writerows(stable_f)

    # ── drift type frequencies ───────────────────────────────────────────
    d_all = [r for r in all_records if r.get('_label') == 'full_pipeline']
    if d_all:
        dtc = {}
        for r in d_all:
            dt = r.get('drift_types', {})
            for k, v in dt.items():
                dtc[k] = dtc.get(k, 0) + v
        tot = sum(dtc.values())
        print("\n" + "=" * 80)
        print(" DRIFT TYPE FREQUENCIES")
        print("=" * 80)
        for dtype, count in sorted(dtc.items()):
            print(f" {dtype}: {count}")
        print(f" Total drift events: {tot}")
        print("=" * 80)
        pv = [r.get('resilience_P', 0) for r in d_all]
        p2v = [r.get('resilience_P2', 0) for r in d_all]
        print(f" Average Resilience P  : {mean(pv):.4f}")
        print(f" Average Resilience P2 : {mean(p2v):.4f}")
        print("=" * 80)

    # ── README ───────────────────────────────────────────────────────────
    if not args.no_readme:
        update_readme(roc_data)

    # ── push ─────────────────────────────────────────────────────────────
    if args.push:
        ts = time.strftime('%Y-%m-%d %H:%M')
        git_push('semantic_only', f'Analyze results {ts}')

    print('\n[Done] Analysis complete.')


if __name__ == '__main__':
    main()