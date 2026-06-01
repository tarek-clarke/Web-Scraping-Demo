#!/usr/bin/env python3
"""Spheron B300 Offline TGI Benchmarking Orchestrator.

Launches the offline TGI docker container, runs the unified sweep matrix via local 
TGI, compiles scientific latency metrics, commits the telemetry locally (since 
Spheron blocks outbound internet), and provides a one-line Mac command to pull 
and push the results to GitHub.
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
        name = raw.split("\n")[0].replace("NVIDIA", "").strip()
        return name.replace(" ", "_")
    except Exception:
        return "B300_VM"

def main():
    gpu_name = get_gpu_name()
    print("================================================================================")
    print(f"[*] Starting Spheron Offline TGI Orchestrator on {gpu_name}")
    print("================================================================================")

    # 1. Start HF TGI Docker Container in 100% Offline Mode
    print("[*] Launching offline Hugging Face TGI Docker container...")
    
    # Check if a TGI container is already running to avoid conflicts
    try:
        active_containers = run_command(["docker", "ps", "--filter", "ancestor=ghcr.io/huggingface/text-generation-inference", "--format", "{{.ID}}"])
        if active_containers:
            print("[*] Detected active TGI container running. Reusing container.")
        else:
            tgi_cmd = [
                "docker", "run", "--gpus", "all", "--shm-size", "1g", "-d", "-p", "8080:80",
                "-v", f"{os.path.expanduser('~')}/.cache/huggingface/hub:/data",
                "ghcr.io/huggingface/text-generation-inference:latest",
                "--model-id", "/data/models--google--gemma-4-31B-it",
                "--max-input-length", "4096",
                "--max-total-tokens", "8192",
                "--offline"
            ]
            run_command(tgi_cmd)
            print("[*] TGI launched. Waiting 45 seconds for model load/warmup...")
            time.sleep(45)
    except Exception as e:
        print(f"[!] Warning: Docker launch failed ({e}). Proceeding to pipeline run directly.")

    # 2. Run the dynamic matrix benchmark
    print("\n[*] Starting matrix sweep pointing to local offline TGI...")
    start_time = time.perf_counter()
    
    env = os.environ.copy()
    env["USE_GEMMA_30B"] = "1"
    env["USE_API"] = "1"
    env["GEMMA_30B_API_URL"] = "http://localhost:8080/v1/chat/completions"
    env["GEMMA_30B_API_MODEL"] = "gemma-4-31B-it"
    
    subprocess.run([sys.executable, "run_matrix_unified.py"], env=env, check=True)
    
    elapsed_total_sec = time.perf_counter() - start_time
    print("\n" + "="*80)
    print("[✓] Sweep execution complete! Compiling scientific performance telemetry...")
    print("="*80)

    # 3. Scanning run_characteristics.json files
    results_root = os.path.join("results", gpu_name)
    if not os.path.exists(results_root):
        results_root = "results"

    run_count = 0
    bert_lats = []
    gemma_lats = []
    gemma30b_lats = []
    
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

    # 4. Construct Dynamically Named Scientific Commit Message
    commit_subject = f"bench(Spheron_{gpu_name}): {run_count}-run sweep complete in {elapsed_total_sec/60:.1f}m"
    commit_body = (
        f"Device: Spheron {gpu_name}\n"
        f"Completed Runs: {run_count} / 80\n"
        f"Gemma 31B (Offline TGI) Avg Latency: {avg_gemma30b:.2f} ms\n"
        f"Gemma 4B Avg Latency: {avg_gemma:.2f} ms\n"
        f"BERT Avg Latency: {avg_bert:.2f} ms\n"
        f"Execution Timestamp: {datetime.now().isoformat()}"
    )

    print(f"\n[*] Staging results and committing locally (Outbound Port 443 is blocked on Spheron)...")
    run_command(["git", "config", "--local", "user.name", "tarek-clarke"])
    run_command(["git", "config", "--local", "user.email", "tarek.clarke15@gmail.com"])
    
    with open("Note", "w") as f:
        f.write(f"Spheron_{gpu_name}")
        
    run_command(["git", "add", "Note"])
    run_command(["git", "add", "-f", "results/"])
    
    commit_cmd = ["git", "commit", "-m", commit_subject, "-m", commit_body]
    run_command(commit_cmd)
    print(f"[✓] Local Git Commit Completed: {commit_subject}")

    print("\n================================================================================")
    print(" [✓] SPHERON SWEEP RUN COMPLETE!")
    print("================================================================================")
    print("Because outbound connections are blocked on your Spheron VM container,")
    print("please run the following single command on your local MacBook terminal")
    print("to pull the committed results off the VM and push them to GitHub automatically:")
    print("")
    print("  rsync -avz -e 'ssh -p PORT' root@IP:~/resilient-rap-framework/results/ ./results/ && git pull origin main && git push origin main")
    print("================================================================================")

if __name__ == "__main__":
    main()
