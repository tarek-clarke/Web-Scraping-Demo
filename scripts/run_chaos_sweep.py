#!/usr/bin/env python3
"""
run_chaos_sweep.py — Automates sweeping different chaos rates (0.5%, 1%, 5%, 10%, 15%, 50%, 100%)
on the Qualifying telemetry dataset.
"""

import os
import sys
import time
import json
import signal
import subprocess
import glob

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
        print("Usage: python3 run_chaos_sweep.py <telemetry_file_path>")
        sys.exit(1)

    telemetry_file = sys.argv[1]
    if not os.path.exists(telemetry_file):
        print(f"ERROR: Telemetry file not found: {telemetry_file}")
        sys.exit(1)

    total_lines = count_lines(telemetry_file)
    print(f"=== Starting Chaos Rate Sweep ===")
    print(f"Input Telemetry File: {telemetry_file}")
    print(f"Total Packets to process: {total_lines:,}\n")

    chaos_rates = [0.005, 0.01, 0.05, 0.10, 0.15, 0.50, 1.00]
    results = []

    reports_dir = "data/reports/live_f1"
    os.makedirs(reports_dir, exist_ok=True)

    for rate in chaos_rates:
        print(f"--- Running sweep for Chaos Rate: {rate*100:.1f}% ---")
        
        # 1. Reset telemetry_latest.json
        latest_file = "data/ingested/telemetry_latest.json"
        if os.path.exists(latest_file):
            os.remove(latest_file)
        with open(latest_file, "w") as f:
            pass

        # 2. Start the decoder in the background
        log_filepath = f"decoder_sweep_{rate}.log"
        log_file = open(log_filepath, "w")
        
        cmd = [
            "python3", "-u", "live_gpu_decoder.py",
            "--reconciler", "bert",
            "--chaos-rate", str(rate),
            "--poll-interval", "0.05",
            "--telemetry-file", latest_file
        ]
        
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file, preexec_fn=os.setsid)
        
        # 3. Wait for the reconciler model to load onto the GPU
        print("Waiting for decoder to initialize and load BERT model...")
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
            print("ERROR: Decoder initialization timed out.")
            proc.terminate()
            log_file.close()
            continue

        print("Decoder initialized. Feeding packets...")
        
        # 4. Feed all packets
        with open(telemetry_file, "r") as src, open(latest_file, "w") as dest:
            dest.write(src.read())

        # 5. Monitor progress
        print("Processing packets...")
        expected_total_str = f"Total: {total_lines:,}"
        completed = False
        start_time = time.time()
        
        for _ in range(600):  # Up to 10 minutes
            time.sleep(1)
            if os.path.exists(log_filepath):
                with open(log_filepath, "r") as f:
                    lines = f.readlines()
                    # Find progress updates in logs
                    for line in reversed(lines):
                        if "Processed" in line and "Total:" in line:
                            print(f"  {line.strip()}")
                            break
                    # Check for completion
                    full_log = "".join(lines)
                    if expected_total_str in full_log:
                        completed = True
                        break
            
            # Check if process died
            if proc.poll() is not None:
                print("WARNING: Decoder process died unexpectedly.")
                break

        if completed:
            print("All packets processed successfully.")
        else:
            print("WARNING: Replay monitor timed out. Terminating job...")

        # Let the decoder write buffers
        time.sleep(3)

        # 6. Stop the decoder gracefully
        print("Stopping decoder gracefully (SIGTERM)...")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception as e:
            print(f"Warning during shutdown: {e}")
            proc.kill()

        log_file.close()

        # 7. Collect results from manifest
        latest_manifest = get_latest_manifest(reports_dir)
        if latest_manifest:
            print(f"Reading manifest: {latest_manifest}")
            with open(latest_manifest, "r") as f:
                manifest = json.load(f)
                
            results.append({
                "chaos_rate": rate,
                "total_packets": manifest.get("total_packets_processed", 0),
                "total_drifted": manifest.get("total_drifted", 0),
                "avg_accuracy": manifest.get("avg_accuracy", 0.0),
                "avg_latency_ms": manifest.get("avg_latency_ms", 0.0),
                "gpu_total_energy_joules": manifest.get("gpu_total_energy_joules", 0.0),
                "gpu_avg_power_watts": manifest.get("gpu_avg_power_watts", 0.0)
            })
            print(f"Result collected: Acc={manifest.get('avg_accuracy', 0.0)*100:.2f}%, Energy={manifest.get('gpu_total_energy_joules', 0.0):,} J\n")
        else:
            print("ERROR: No manifest found for this sweep run.\n")

    # Write summary CSV
    summary_path = os.path.join(reports_dir, "chaos_sweep_results.csv")
    with open(summary_path, "w") as f:
        f.write("chaos_rate,total_packets,total_drifted,avg_accuracy,avg_latency_ms,gpu_total_energy_joules,gpu_avg_power_watts\n")
        for res in results:
            f.write(f"{res['chaos_rate']},{res['total_packets']},{res['total_drifted']},{res['avg_accuracy']},{res['avg_latency_ms']},{res['gpu_total_energy_joules']},{res['gpu_avg_power_watts']}\n")
    
    print("=" * 60)
    print("  SWEEP COMPLETE")
    print("=" * 60)
    print(f"Results saved to: {summary_path}\n")

    # Print summary markdown table
    print("| Chaos Rate (%) | Total Packets | Drifted Packets | Avg. Accuracy | Avg. Latency (ms) | GPU Energy (Joules) | Avg. Power (W) |")
    print("| :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for res in results:
        print(f"| {res['chaos_rate']*100:.1f}% | {res['total_packets']:,} | {res['total_drifted']:,} | {res['avg_accuracy']*100:.2f}% | {res['avg_latency_ms']:.3f} | {res['gpu_total_energy_joules']:,} | {res['gpu_avg_power_watts']:.2f} |")
    print("=" * 60)

if __name__ == "__main__":
    main()
