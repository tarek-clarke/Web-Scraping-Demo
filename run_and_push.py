#!/usr/bin/env python3
"""High-Performance Benchmark Orchestrator & Auto-Publisher.

Executes the unified 80-run matrix sweep, dynamically compiles real-time 
performance metrics (latencies for Gemma 31B, Gemma 4B, BERT), and pushes 
telemetry logs to GitHub with a rich, dynamically formatted commit message.
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime, timedelta

def run_command(cmd, shell=False):
    """Run a shell command and return stdout. Exit on failure."""
    try:
        res = subprocess.run(cmd, shell=shell, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[!] Command failed: {e.cmd}")
        print(f"    Stdout: {e.stdout}")
        print(f"    Stderr: {e.stderr}")
        sys.exit(1)

def get_gpu_name():
    """Query nvidia-smi for precise GPU model name."""
    try:
        raw = run_command(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"])
        # Format "NVIDIA GeForce RTX 5090" -> "RTX_5090"
        name = raw.split("\n")[0].replace("NVIDIA", "").replace("GeForce", "").strip()
        return name.replace(" ", "_")
    except Exception:
        return "CPU_Fallback"

def main():
    print("================================================================================")
    # 1. Determine GPU and launch Sweep
    gpu_name = get_gpu_name()
    print(f"[*] Starting Sweep Execution on {gpu_name} ({datetime.now().isoformat()})...")
    print("================================================================================")
    
    start_time = time.perf_counter()
    
    # Run matrix sweep
    env = os.environ.copy()
    env["USE_GEMMA_30B"] = "1"
    # Ensure stdout streams live to the terminal
    subprocess.run([sys.executable, "run_matrix_unified.py"], env=env, check=True)
    
    elapsed_total_sec = time.perf_counter() - start_time
    print("\n" + "="*80)
    print("[✓] Sweep execution complete! Compiling scientific performance telemetry...")
    print("="*80)

    # 2. Dynamically scan recent run folders to calculate average latencies
    results_root = os.path.join("results", gpu_name)
    if not os.path.exists(results_root):
        # Handle cases where folder is named differently
        results_root = "results"

    run_count = 0
    bert_lats = []
    gemma_lats = []
    gemma30b_lats = []
    
    # We only scan characteristics files written in the last 2 hours (this execution)
    cutoff = datetime.now() - timedelta(hours=2)
    
    for root, dirs, files in os.walk(results_root):
        if "run_characteristics.json" in files:
            char_path = os.path.join(root, "run_characteristics.json")
            mtime = datetime.fromtimestamp(os.path.getmtime(char_path))
            if mtime > cutoff:
                try:
                    with open(char_path, "r") as f:
                        data = json.load(f)
                        run_count += 1
                        if data.get("bert_average_latency_ms"):
                            bert_lats.append(data["bert_average_latency_ms"])
                        if data.get("gemma_average_latency_ms"):
                            gemma_lats.append(data["gemma_average_latency_ms"])
                        if data.get("gemma30b_average_latency_ms"):
                            gemma30b_lats.append(data["gemma30b_average_latency_ms"])
                except Exception:
                    pass

    # Compute averages
    avg_bert = sum(bert_lats) / len(bert_lats) if bert_lats else 0.0
    avg_gemma = sum(gemma_lats) / len(gemma_lats) if gemma_lats else 0.0
    avg_gemma30b = sum(gemma30b_lats) / len(gemma30b_lats) if gemma30b_lats else 0.0
    
    # 3. Construct Dynamically Named Scientific Commit Message
    commit_subject = f"bench({gpu_name}): {run_count}-run sweep complete in {elapsed_total_sec/60:.1f}m"
    commit_body = (
        f"Device: {gpu_name}\n"
        f"Completed Runs: {run_count} / 80\n"
        f"Gemma 31B (MoE) Avg Latency: {avg_gemma30b:.2f} ms\n"
        f"Gemma 4B Avg Latency: {avg_gemma:.2f} ms\n"
        f"BERT Avg Latency: {avg_bert:.2f} ms\n"
        f"System Hostname: {run_command(['hostname'])}\n"
        f"Execution Timestamp: {datetime.now().isoformat()}"
    )
    
    print(f"\n[*] Compiled Dynamic Commit Message:\nSubject: {commit_subject}\nBody:\n{commit_body}\n")

    # 4. Git Stage, Commit, and Auto-Push
    print("[*] Staging telemetry files and pushing to GitHub...")
    # Configure dynamic local Git identifiers for Vast.ai environment stability
    run_command(["git", "config", "--local", "user.name", "tarek-clarke"])
    run_command(["git", "config", "--local", "user.email", "tarek.clarke15@gmail.com"])
    
    # Write hardware name to the Note file
    with open("Note", "w") as f:
        f.write(gpu_name)
    
    # Add files
    run_command(["git", "add", "Note"])
    run_command(["git", "add", "-f", "results/"])
    
    # Create git commit command
    commit_cmd = ["git", "commit", "-m", commit_subject, "-m", commit_body]
    run_command(commit_cmd)
    
    # Push to origin
    print("[*] Publishing datasets to origin main...")
    run_command(["git", "push", "origin", "main"])
    
    print("\n================================================================================")
    print(f"[✓] SUCCESS! Telemetry published successfully in {elapsed_total_sec/60:.1f} minutes.")
    print("================================================================================")

if __name__ == "__main__":
    main()
