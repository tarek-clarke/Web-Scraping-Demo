import os
import sys
import json
import time
import csv
from models.device_selector import get_device_info
from tests.run_experiments import ExperimentRunner

def run_evaluation_pipeline():
    if '--bootstrap' in sys.argv:
        import bootstrap
        bootstrap.run_bootstrap(force=True)

    g = time.perf_counter()
    d = get_device_info()
    h = d['model'].replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
    c = d['cloud']
    print('\n' + '=' * 80)
    print(' Hey! Welcome to the Semantic Drift Evaluation Pipeline Runner')
    print(f' Hardware Platform : {d["device"].upper()}')
    print(f' Hardware Model    : {d["model"]}')
    print(f' Cloud Environment : {d["cloud"].upper()}')
    print('=' * 80 + '\n')

    e = '--erase-existing' in sys.argv or '--force-erase' in sys.argv
    R = f'results/{h}/{c}'
    if e:
        if os.path.exists(R):
            import shutil
            print(f'[Runner] Removing existing results at {R} (flag provided).')
            shutil.rmtree(R)
    else:
        try:
            p = input(f'Erase existing results at {R}? [y/N]: ')
            if p.strip().lower() in ('y', 'yes'):
                import shutil
                if os.path.exists(R):
                    print(f'[Runner] Removing existing results at {R}.')
                    shutil.rmtree(R)
                else:
                    print(f'[Runner] No existing results found at {R}.')
        except:
            pass
    r = ExperimentRunner()
    if '--force-rerun' in sys.argv:
        r.force_rerun = True
        print('[Pipeline] Force rerun enabled.')

    P = ['short', 'long']
    F = ['100hz', '1000hz', '1mhz']
    X = ['json', 'schema', 'gemma']
    L = ['high', 'medium', 'low']
    A = ['finnhub', 'openmeteo', 'spacex', 'openf1']
    C = [1]

    n = len(P) * len(F) * len(X) * len(L) * len(A) * len(C)
    N = n * 4
    print(f'[Pipeline] Scheduled {n} distinct configurations (4 runs each, total {N} evaluation streams).')
    print('[Pipeline] Running evaluation pipeline (this runs incrementally, skipping existing runs)...')
    t = []
    cnt = 0
    all_res = []
    for p in P:
        for f in F:
            for x in X:
                for l in L:
                    for a in A:
                        for co in C:
                            cnt += 1
                            print(f'[Pipeline] Progress: {cnt}/{n} ({(cnt / n) * 100.0:.1f}%) | Config: {a} - {f} - {x} {l} - Concurrency: {co}')
                            for rn in [1, 2, 3, 4]:
                                try:
                                    if co == 1:
                                        res = r.run_single_stream(
                                            api_name=a,
                                            packet_profile=p,
                                            frequency_profile=f,
                                            chaos_strategy=x,
                                            chaos_level=l,
                                            run_number=rn,
                                            concurrency=1
                                        )
                                        if res and 'total_runtime_sec' in res:
                                            t.append(res['total_runtime_sec'])
                                            all_res.append(res)
                                    else:
                                        # concurrency >1 not implemented in this version
                                        pass
                                except Exception as e:
                                    print(f'[Pipeline] [ERROR] Failed on config: {e}')
    ge = time.perf_counter()
    gr = ge - g

    sd = f'results/{h}/{c}'
    os.makedirs(sd, exist_ok=True)
    sp = os.path.join(sd, 'summary.json')

    total_t = sum(t)
    avg_t = total_t // max(1, len(t)) if t else 0
    fast_t = min(t) if t else 0
    slow_t = max(t) if t else 0

    d_d = [r.get('detection_rate', 0) for r in all_res if r]
    d_l = [r.get('p95_latency_ms', 0) for r in all_res if r]
    s_r = [r for r in all_res if r and r.get('run_number', 1) > 1]
    s_d = [r.get('detection_rate', 0) for r in s_r]
    s_l = [r.get('p95_latency_ms', 0) for r in s_r]

    def avg_i(x):
        return sum(x) // max(1, len(x))

    m_c = {'detection_rate': avg_i(d_d), 'p95_latency_ms': avg_i(d_l)} if d_d else {}
    s_m = {'detection_rate': avg_i(s_d), 'p95_latency_ms': avg_i(s_l)} if s_d else {}

    data = {
        'global_runtime_sec': round(gr, 4),
        'total_runs_time_sec': round(total_t, 4),
        'average_runtime_sec': avg_t,
        'fastest_run_sec': fast_t,
        'slowest_run_sec': slow_t,
        'total_runs_count': len(t),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'mean_with_cold_start': m_c,
        'stable_mean': s_m
    }
    with open(sp, 'w') as f:
        json.dump(data, f, indent=2)
    print(f'\n[Pipeline] Completed all evaluations in {gr:.2f} seconds.')
    print(f'Cold start mean detection_rate: {m_c.get("detection_rate")}, p95_latency_ms: {m_c.get("p95_latency_ms")}')
    print(f'Stable mean detection_rate: {s_m.get("detection_rate")}, p95_latency_ms: {s_m.get("p95_latency_ms")}')

    # Flatten results
    flat_all = []
    for r in all_res:
        flat = {}
        for k, v in r.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    flat[f'{k}_{kk}'] = vv
            else:
                flat[k] = v
        flat_all.append(flat)

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

    # Global unified
    gal = []
    gst = []
    for e in os.listdir('results/'):
        if os.path.isdir('results/' + e):
            fp = 'results/' + e + '/master_platform_all_runs_1_to_4.json'
            if os.path.exists(fp):
                with open(fp) as f:
                    rd = json.load(f)
                    gal.extend(rd)
            fp2 = 'results/' + e + '/master_platform_stable_runs_2_to_4.json'
            if os.path.exists(fp2):
                with open(fp2) as f:
                    rd = json.load(f)
                    gst.extend(rd)
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

    # Print final summary with drift type frequencies
    if all_res:
        drift_type_counter = {}
        for r in all_res:
            dt = r.get('drift_types', {})
            for k, v in dt.items():
                drift_type_counter[k] = drift_type_counter.get(k, 0) + v
        total_drift_events = sum(drift_type_counter.values())
        print("\n" + "=" * 80)
        print(" DRIFT TYPE FREQUENCIES")
        print("=" * 80)
        for dtype, count in drift_type_counter.items():
            print(f" {dtype}: {count}")
        print(f" Total drift events: {total_drift_events}")
        print("=" * 80)

        p_vals = [r.get('resilience_P', 0) for r in all_res]
        p2_vals = [r.get('resilience_P2', 0) for r in all_res]
        avg_p = sum(p_vals) / max(1, len(p_vals))
        avg_p2 = sum(p2_vals) / max(1, len(p2_vals))
        print(f" Average Resilience P  : {avg_p:.3f}")
        print(f" Average Resilience P2 : {avg_p2:.3f}")
        print("=" * 80)


if __name__ == '__main__':
    run_evaluation_pipeline()
