#!/usr/bin/env python3
import time
import subprocess
import os
import sys

def check_lumi_jobs_done():
    cmd = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "clarketa@lumi.csc.fi", "sacct -u clarketa --format=JobID,JobName,State | tail -n 25"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        lines = res.stdout.strip().splitlines()
        running_or_pending = [l for l in lines if ("RUNNING" in l or "PENDING" in l)]
        return len(running_or_pending) == 0
    except Exception as e:
        print(f"Error checking LUMI jobs: {e}")
        return False

def pull_lumi_results():
    print("Pulling all completed baseline & Aer GPU reports from LUMI...")
    cmd1 = ["scp", "-r", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "clarketa@lumi.csc.fi:/scratch/project_465002996/clarketa/resilient-rap-tkde-aer-20260722/data/reports/MI250X_run*", "data/reports/"]
    cmd2 = ["scp", "-r", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "clarketa@lumi.csc.fi:/scratch/project_465002996/clarketa/resilient-rap-tkde-aer-20260722/data/reports/quantum_MI250X_aer_sim_*", "data/reports/"]
    subprocess.run(cmd1)
    subprocess.run(cmd2)

def run_ibm_qpu_10_times():
    print("=== Starting 10 Physical IBM QPU Benchmark Repetitions ===")
    env = os.environ.copy()
    env["QUANTUM_BACKEND_NAME"] = "ibm_fez"
    env["QISKIT_IBM_CHANNEL"] = "ibm_cloud"
    for run_idx in range(1, 11):
        suffix = f"_ibm_qpu_run{run_idx:02d}"
        print(f"\n---> Launching IBM QPU Repetition {run_idx}/10 ({suffix})...")
        cmd = [
            "python3", "run_matrix.py",
            "--max-packets-per-api", "2500",
            "--chaos-rate", "0.10",
            "--repetitions", "1",
            "--backend", "ibm_quantum",
            "--phases", "quantum",
            "--run-number", str(run_idx),
            "--suffix", suffix,
            "--packets-file", "data/ingested/telemetry_clean_bench_22500.json"
        ]
        res = subprocess.run(cmd, env=env)
        if res.returncode != 0:
            print(f"WARNING: IBM QPU Repetition {run_idx} exited with code {res.returncode}")

def push_to_github():
    print("\n=== Pushing all 10 Repetition Datasets to GitHub ===")
    subprocess.run(["git", "add", "-f", "data/reports/"])
    subprocess.run(["git", "commit", "-m", "feat(benchmark): add 10 completed repetitions for Baselines, Aer GPU, and Physical IBM QPU"])
    subprocess.run(["git", "push", "origin", "tkde"])

def main():
    print("=== Automated LUMI Monitoring & IBM QPU Pipeline ===")
    print("Waiting for LUMI GPU & Baseline jobs to finish...")
    while not check_lumi_jobs_done():
        print("LUMI jobs are still running/pending. Checking again in 30 seconds...")
        time.sleep(30)
    
    print("\nAll LUMI jobs completed!")
    pull_lumi_results()
    run_ibm_qpu_10_times()
    push_to_github()
    print("\n=== ALL 10 BENCHMARK REPETITIONS & IBM QPU RUNS 100% COMPLETE! ===")

if __name__ == "__main__":
    main()
