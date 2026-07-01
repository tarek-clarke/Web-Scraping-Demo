#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hardware.power_profiler import GPUPowerProfiler

def run_matrix_phase(phase, run_matrix_args):
    print(f"\n==================================================")
    print(f"  Profiling Phase: {phase}")
    print(f"==================================================")
    
    profiler = GPUPowerProfiler(interval_sec=0.05)
    profiler.start()
    
    # Run the matrix comparison command
    cmd = [sys.executable, "run_matrix.py"] + run_matrix_args + ["--phases", phase]
    print(f"Executing: {' '.join(cmd)}")
    
    t_start = time.perf_counter()
    subprocess.run(cmd, check=True)
    duration = time.perf_counter() - t_start
    
    metrics = profiler.stop()
    print(f"\n--- Results for {phase} ---")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Total GPU Energy Consumed: {metrics['total_joules']:,} Joules")
    print(f"Average GPU Power Draw: {metrics['avg_watts']:.2f} Watts")
    
    return {
        "phase": phase,
        "runtime_seconds": round(duration, 2),
        "total_joules": metrics["total_joules"],
        "avg_watts": metrics["avg_watts"],
        "samples": metrics["samples_count"]
    }

def main():
    if not os.path.exists("run_matrix.py"):
        print("ERROR: Run this script from the project root directory.")
        sys.exit(1)
        
    os.makedirs("data/reports", exist_ok=True)
    
    # Base arguments for matrix run
    run_args = ["--max-packets-per-api", "200", "--chaos-rate", "0.10", "--repetitions", "1"]
    
    # 1. Profile brute-force BERT (GPU heavy)
    bert_metrics = run_matrix_phase("bert", run_args)
    
    # 2. Profile hybrid quantum routing (GPU light, CPU fallback)
    # Uses local AerSimulator
    quantum_metrics = run_matrix_phase("quantum", run_args + ["--backend", "aer_simulator"])
    
    # Calculate energy efficiency metrics
    energy_saved_joules = bert_metrics["total_joules"] - quantum_metrics["total_joules"]
    pct_reduction = (energy_saved_joules / max(bert_metrics["total_joules"], 1)) * 100
    
    comparison = {
        "bert_only": bert_metrics,
        "quantum_routed": quantum_metrics,
        "savings": {
            "energy_saved_joules": round(energy_saved_joules, 2),
            "percentage_reduction": round(pct_reduction, 2)
        }
    }
    
    print("\n==================================================")
    print("  FINAL ENERGY SAVINGS COMPARISON")
    print("==================================================")
    print(f"BERT GPU-Only:      {bert_metrics['total_joules']:,} Joules")
    print(f"Quantum-Routed:     {quantum_metrics['total_joules']:,} Joules")
    print(f"Energy Saved:       {energy_saved_joules:,} Joules ({pct_reduction:.1f}% reduction)")
    print("==================================================")
    
    output_path = "data/reports/gpu_energy_comparison.json"
    with open(output_path, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"Detailed energy report written to {output_path}")

if __name__ == "__main__":
    main()
