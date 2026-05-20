import os
import sys
import time
import json
from models.device_selector import get_device_info
from tests.run_experiments import ExperimentRunner

def run_evaluation_pipeline():
    # Force bootstrap if passed via cmd line arguments
    force_bootstrap = "--bootstrap" in sys.argv
    import bootstrap
    bootstrap.run_bootstrap(force=force_bootstrap)

    global_start = time.perf_counter()
    
    device_info = get_device_info()
    hardware_model = device_info["model"].replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
    cloud = device_info["cloud"]

    print("\n" + "="*80)
    print(" SEMANTIC DRIFT EVALUATION FRAMEWORK - UNIFIED PIPELINE RUNNER")
    print(f" Hardware Platform : {device_info['device'].upper()}")
    print(f" Hardware Model    : {device_info['model']}")
    print(f" Cloud Environment : {device_info['cloud'].upper()}")
    print("="*80 + "\n")

    # Provide an option to erase previous runs. Use CLI flag to skip prompt.
    erase_flag = "--erase-existing" in sys.argv or "--force-erase" in sys.argv
    results_root = f"results/{hardware_model}/{cloud}"
    if erase_flag:
        if os.path.exists(results_root):
            import shutil
            print(f"[Runner] Removing existing results at {results_root} (flag provided).")
            shutil.rmtree(results_root)
    else:
        try:
            # Interactive prompt to ask user whether to clear previous runs
            resp = input(f"Erase existing results at {results_root}? This will delete previous runs. [y/N]: ")
            if resp.strip().lower() in ("y", "yes"):
                import shutil
                if os.path.exists(results_root):
                    print(f"[Runner] Removing existing results at {results_root}.")
                    shutil.rmtree(results_root)
                else:
                    print(f"[Runner] No existing results found at {results_root}.")
        except Exception:
            # Non-interactive environments may raise; continue without deleting
            pass

    # Enforce optimized execution matrix (72 configurations, 3-run rule, total 216 runs)
    runner = ExperimentRunner()
    
    packet_profiles = ["short", "long"]
    frequency_profiles = ["100hz"]
    chaos_strategies = ["json", "schema", "gemma"]
    chaos_levels = ["high", "medium", "low"]
    apis = ["finnhub", "openmeteo", "spacex", "openf1"]
    concurrency_modes = [1]

    total_configs = len(packet_profiles) * len(frequency_profiles) * len(chaos_strategies) * len(chaos_levels) * len(apis) * len(concurrency_modes)
    total_runs = total_configs * 3
    
    # Check if C++ acceleration is active
    try:
        import cpp_accel
        cpp_active = cpp_accel is not None
    except ImportError:
        cpp_active = False

    # Dynamic estimation parameters
    is_gpu = device_info["device"].upper() in ["CUDA", "ROCM", "MPS"]
    
    # Calculate estimations based on backend
    if cpp_active:
        if is_gpu:
            est_short_sec = 0.5
            est_long_sec = 10.0
            accel_label = "C++ Acceleration + GPU Enabled"
        else:
            est_short_sec = 1.5
            est_long_sec = 40.0
            accel_label = "C++ Acceleration (CPU Fallback)"
    else:
        if is_gpu:
            est_short_sec = 4.0
            est_long_sec = 250.0
            accel_label = "Python Standard (GPU Only)"
        else:
            est_short_sec = 15.0
            est_long_sec = 1200.0
            accel_label = "Python Standard (CPU Fallback)"

    # Total projected runtimes (72 configurations * 3 runs = 216 runs)
    # 36 configs are "short", 36 are "long"
    n_short_runs = 36 * 3
    n_long_runs = 36 * 3
    
    projected_sec = (n_short_runs * est_short_sec) + (n_long_runs * est_long_sec)
    projected_hours = projected_sec / 3600.0
    
    # Baseline worst-case comparison (CPU Fallback with Python loop)
    worst_case_sec = (n_short_runs * 15.0) + (n_long_runs * 1200.0)
    worst_case_hours = worst_case_sec / 3600.0

    print("\n" + "="*80)
    print("                     EXECUTION RUNTIME ESTIMATION CHART")
    print("="*80)
    print(f" Detected Backend : {device_info['device'].upper()} ({device_info['model']})")
    print(f" Optimization     : {accel_label}")
    print(f" Configurations   : {total_configs} distinct configs (3 runs each, total {total_runs} streams)")
    print("-"*80)
    print(" ESTIMATED TIME PER RUN BY PROFILE:")
    print(f"  - Sprint Profile (30k packets)  : ~{est_short_sec:.2f} seconds")
    print(f"  - Weekend Profile (3M packets) : ~{est_long_sec:.2f} seconds")
    print("-"*80)
    print(" PROJECTED PIPELINE COMPLETION TIME COMPARISON:")
    
    # Visual bar charts
    worst_bar_len = 20
    worst_bar = "█" * worst_bar_len
    
    accel_bar_len = max(1, int((projected_sec / worst_case_sec) * worst_bar_len))
    accel_bar = "█" * accel_bar_len + " " * (worst_bar_len - accel_bar_len)
    
    print(f"  - Standard Python (CPU fallback) : [{worst_bar}] ~{worst_case_hours:.1f} hours")
    print(f"  - C++ Accelerated Suite (Ours)   : [{accel_bar}] ~{projected_hours:.2f} hours")
    print("-"*80)
    print(" NOTE: Existing completed runs will be skipped dynamically.")
    print("="*80 + "\n")
    
    print(f"[Pipeline] Scheduled {total_configs} distinct configurations (3 runs each, total {total_runs} evaluation streams).")
    print("[Pipeline] Running evaluation pipeline (this runs incrementally, skipping existing runs)...")
    
    run_times = []
    config_count = 0
    
    for p_profile in packet_profiles:
        for f_profile in frequency_profiles:
            for strategy in chaos_strategies:
                for level in chaos_levels:
                    for api_name in apis:
                        for concurrency in concurrency_modes:
                            config_count += 1
                            print(f"[Pipeline] Progress: {config_count}/{total_configs} ({(config_count/total_configs)*100.0:.1f}%) | Config: {api_name} - {f_profile} - {strategy} {level} - Concurrency: {concurrency}")
                            
                            # Execute 3 runs (3-run rule)
                            for run_n in [1, 2, 3]:
                                try:
                                    if concurrency == 1:
                                        res = runner.run_single_stream(
                                            api_name=api_name,
                                            packet_profile=p_profile,
                                            frequency_profile=f_profile,
                                            chaos_strategy=strategy,
                                            chaos_level=level,
                                            run_number=run_n,
                                            concurrency=1
                                        )
                                        if res and "total_runtime_sec" in res:
                                            run_times.append(res["total_runtime_sec"])
                                    else:
                                        res = runner.run_concurrent_streams(
                                            api_name=api_name,
                                            packet_profile=p_profile,
                                            frequency_profile=f_profile,
                                            chaos_strategy=strategy,
                                            chaos_level=level,
                                            run_number=run_n
                                        )
                                        if res:
                                            if "stream_1" in res and "total_runtime_sec" in res["stream_1"]:
                                                run_times.append(res["stream_1"]["total_runtime_sec"])
                                            if "stream_2" in res and "total_runtime_sec" in res["stream_2"]:
                                                run_times.append(res["stream_2"]["total_runtime_sec"])
                                except Exception as e:
                                    print(f"[Pipeline] [ERROR] Failed on config: {e}")
                                    
    global_end = time.perf_counter()
    global_runtime_sec = global_end - global_start
    
    # Save global_runtime_sec and stats to results/<hardware>/<cloud>/summary.json
    summary_dir = f"results/{hardware_model}/{cloud}"
    os.makedirs(summary_dir, exist_ok=True)
    summary_path = os.path.join(summary_dir, "summary.json")
    
    total_runs_time = sum(run_times)
    avg_run_time = total_runs_time / len(run_times) if run_times else 0.0
    fastest_run = min(run_times) if run_times else 0.0
    slowest_run = max(run_times) if run_times else 0.0
    
    summary_data = {
        "global_runtime_sec": round(global_runtime_sec, 4),
        "total_runs_time_sec": round(total_runs_time, 4),
        "average_runtime_sec": round(avg_run_time, 4),
        "fastest_run_sec": round(fastest_run, 4),
        "slowest_run_sec": round(slowest_run, 4),
        "total_runs_count": len(run_times),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    with open(summary_path, "w") as f:
        json.dump(summary_data, f, indent=2)
        
    print(f"\n[Pipeline] Completed all evaluations in {global_runtime_sec:.2f} seconds.")
    print("\n" + "="*80)
    print("                      GLOBAL RUNTIME SUMMARY")
    print("="*80)
    print(f" Total pipeline duration    : {global_runtime_sec:.2f} seconds")
    print(f" Total individual runs counted : {len(run_times)}")
    print(f" Combined runtime of all runs  : {total_runs_time:.2f} seconds")
    print(f" Average runtime per run       : {avg_run_time:.4f} seconds")
    print(f" Fastest run duration          : {fastest_run:.4f} seconds")
    print(f" Slowest run duration          : {slowest_run:.4f} seconds")
    print("="*80 + "\n")
    
    # Run performance reporting scripts to output the validation tables
    from tests.performance.baseline_latency import print_baseline_latency
    from tests.performance.concurrency_scaling import print_concurrency_scaling
    from tests.performance.frequency_stability import print_frequency_stability
    from tests.performance.llm_chaos_comparison import print_llm_chaos_comparison
    
    print("\n" + "="*80)
    print("                     EVALUATION PIPELINE RESULTS SUMMARY")
    print("="*80)
    
    print_baseline_latency()
    print_concurrency_scaling()
    print_frequency_stability()
    print_llm_chaos_comparison()

if __name__ == "__main__":
    run_evaluation_pipeline()
