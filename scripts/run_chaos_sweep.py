#!/usr/bin/env python3
"""
run_chaos_sweep.py — Automates sweeping different chaos rates (0.5%, 1%, 5%, 10%, 15%, 50%, 100%)
on the Qualifying or Grand Prix telemetry dataset, repeating each run N times to compile
statistical mean and standard deviation for all performance metrics.
"""

import os
import sys
import time
import json
import signal
import subprocess
import glob
import numpy as np

def get_latest_manifest(reports_dir):
    manifests = glob.glob(os.path.join(reports_dir, "manifest_*.json"))
    if not manifests:
        return None
    # Sort by modification time
    manifests.sort(key=os.path.getmtime)
    return manifests[-1]

def count_lines(filepath):
    with open(filepath, "r") as f:
        return sum(1 for _ in f)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 run_chaos_sweep.py <telemetry_file_path> [num_runs]")
        sys.exit(1)

    telemetry_file = sys.argv[1]
    if not os.path.exists(telemetry_file):
        print(f"ERROR: Telemetry file not found: {telemetry_file}")
        sys.exit(1)

    num_runs = 5
    if len(sys.argv) >= 3:
        try:
            num_runs = int(sys.argv[2])
        except ValueError:
            print(f"Warning: Invalid num_runs arg, defaulting to 5")

    chaos_method = "qwen_chaos"
    if len(sys.argv) >= 4:
        chaos_method = sys.argv[3]

    total_lines = count_lines(telemetry_file)
    print(f"=== Starting Multi-Run Chaos Rate Sweep ===")
    print(f"Input Telemetry File: {telemetry_file}")
    print(f"Total Packets per Run: {total_lines:,}")
    print(f"Runs per Chaos Rate: {num_runs}")
    print(f"Chaos Method: {chaos_method}\n")

    chaos_rates = [0.005, 0.01, 0.05, 0.10, 0.15, 0.50, 1.00]
    aggregated_results = []

    reports_dir = "data/reports/live_f1"
    os.makedirs(reports_dir, exist_ok=True)

    for rate in chaos_rates:
        print(f"--- Sweeping Chaos Rate: {rate*100:.1f}% ({num_runs} runs) ---")
        
        run_accuracies = []
        run_latencies = []
        run_energies = []
        run_powers = []
        drift_count = 0
        total_packets = total_lines

        for run_idx in range(1, num_runs + 1):
            print(f"  [Run {run_idx}/{num_runs}] Initializing decoder...")
            
            # 1. Reset telemetry_latest.json
            latest_file = "data/ingested/telemetry_latest.json"
            if os.path.exists(latest_file):
                os.remove(latest_file)
            with open(latest_file, "w") as f:
                pass

            # 2. Start the decoder in the background
            log_filepath = f"decoder_sweep_{rate}_run{run_idx}.log"
            log_file = open(log_filepath, "w")
            
            cmd = [
                "python3", "-u", "live_gpu_decoder.py",
                "--reconciler", "bert",
                "--chaos-rate", str(rate),
                "--chaos-method", chaos_method,
                "--poll-interval", "0.05",
                "--telemetry-file", latest_file
            ]
            
            proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file, preexec_fn=os.setsid)
            
            # 3. Wait for the reconciler model to load onto the GPU
            initialized = False
            for _ in range(300):  # Up to 300 seconds
                time.sleep(1)
                if os.path.exists(log_filepath):
                    with open(log_filepath, "r") as f:
                        content = f.read()
                        if "Reconciler ready." in content:
                            initialized = True
                            break
            
            if not initialized:
                print(f"    ERROR: Decoder initialization timed out on Run {run_idx}.")
                proc.terminate()
                log_file.close()
                continue

            # 4. Feed all packets
            with open(telemetry_file, "r") as src, open(latest_file, "w") as dest:
                dest.write(src.read())

            # 5. Monitor progress
            expected_total_str = f"Total: {total_lines:,}"
            completed = False
            
            for _ in range(600):  # Up to 10 minutes
                time.sleep(1)
                if os.path.exists(log_filepath):
                    with open(log_filepath, "r") as f:
                        full_log = f.read()
                        if expected_total_str in full_log:
                            completed = True
                            break
                
                # Check if process died
                if proc.poll() is not None:
                    break

            # Let the decoder write buffers
            time.sleep(2)

            # 6. Stop the decoder gracefully
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=10)
            except Exception:
                proc.kill()

            log_file.close()

            # 7. Collect results from manifest
            latest_manifest = get_latest_manifest(reports_dir)
            if latest_manifest and completed:
                with open(latest_manifest, "r") as f:
                    manifest = json.load(f)
                
                run_accuracies.append(manifest.get("avg_accuracy", 0.0))
                run_latencies.append(manifest.get("avg_latency_ms", 0.0))
                run_energies.append(manifest.get("gpu_total_energy_joules", 0.0))
                run_powers.append(manifest.get("gpu_avg_power_watts", 0.0))
                drift_count = manifest.get("total_drifted", 0)
                total_packets = manifest.get("total_packets_processed", total_lines)
                print(f"    Success: Acc={manifest.get('avg_accuracy', 0.0)*100:.2f}%, Energy={manifest.get('gpu_total_energy_joules', 0.0):.1f} J")
            else:
                print(f"    ERROR: Run {run_idx} failed to compile or time out.")

        # Compute stats for this rate
        if run_accuracies:
            aggregated_results.append({
                "chaos_rate": rate,
                "total_packets": total_packets,
                "total_drifted": drift_count,
                "accuracy_mean": np.mean(run_accuracies),
                "accuracy_std": np.std(run_accuracies),
                "latency_mean": np.mean(run_latencies),
                "latency_std": np.std(run_latencies),
                "energy_mean": np.mean(run_energies),
                "energy_std": np.std(run_energies),
                "power_mean": np.mean(run_powers),
                "power_std": np.std(run_powers)
            })
        else:
            print(f"ERROR: All runs failed for chaos rate {rate}")

    # Write summary CSV
    summary_path = os.path.join(reports_dir, "chaos_sweep_results_aggregated.csv")
    with open(summary_path, "w") as f:
        f.write("chaos_rate,total_packets,total_drifted,accuracy_mean,accuracy_std,latency_mean_ms,latency_std_ms,energy_mean_joules,energy_std_joules,power_mean_watts,power_std_watts\n")
        for res in aggregated_results:
            f.write(f"{res['chaos_rate']},{res['total_packets']},{res['total_drifted']},"
                    f"{res['accuracy_mean']},{res['accuracy_std']},"
                    f"{res['latency_mean']},{res['latency_std']},"
                    f"{res['energy_mean']},{res['energy_std']},"
                    f"{res['power_mean']},{res['power_std']}\n")
    
    print("\n" + "=" * 60)
    print("  AGGREGATED SWEEP COMPLETE")
    print("=" * 60)
    print(f"Aggregated results saved to: {summary_path}\n")

    # Print summary markdown table
    print("| Chaos Rate (%) | Total Packets | Drifted Packets | Avg. Accuracy | Avg. Latency (ms) | GPU Energy (Joules) | Avg. Power (W) |")
    print("| :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for res in aggregated_results:
        print(f"| {res['chaos_rate']*100:.1f}% | {res['total_packets']:,} | {res['total_drifted']:,} | "
              f"{res['accuracy_mean']*100:.2f}% ± {res['accuracy_std']*100:.2f}% | "
              f"{res['latency_mean']:.3f} ± {res['latency_std']:.3f} | "
              f"{res['energy_mean']:.1f} ± {res['energy_std']:.1f} | "
              f"{res['power_mean']:.2f} ± {res['power_std']:.2f} |")
    print("=" * 60)

if __name__ == "__main__":
    main()
