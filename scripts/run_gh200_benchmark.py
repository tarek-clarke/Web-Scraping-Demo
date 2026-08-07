#!/usr/bin/env python3
"""
NVIDIA GH200 Grace Hopper Benchmark Suite
Resilient RAP Framework - Methodology-Preserving Hardware Comparison
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.hardware.detector import HardwareDetector
from src.hardware.vram_prober import VRAMProber
from run_matrix import main as run_matrix_main

# Baseline MI250X Metrics from Manuscript
MI250X_BASELINE = {
    "reconcilers": {
        "levenshtein": {"latency_ms": 0.34, "throughput_pps": 2917.3, "cpu_util": 12.5, "gpu_util": 0.0},
        "regex": {"latency_ms": 0.62, "throughput_pps": 1606.3, "cpu_util": 15.0, "gpu_util": 0.0},
        "bert_1gpu": {"latency_ms": 36.75, "throughput_pps": 27.2, "cpu_util": 8.5, "gpu_util": 78.2},
        "bert_4gpu": {"latency_ms": 4.59, "throughput_pps": 217.7, "cpu_util": 24.0, "gpu_util": 94.5},
        "bge_1gpu": {"latency_ms": 38.53, "throughput_pps": 26.0, "cpu_util": 9.0, "gpu_util": 81.4},
        "bge_4gpu": {"latency_ms": 4.82, "throughput_pps": 207.6, "cpu_util": 25.5, "gpu_util": 95.8},
        "cohere": {"latency_ms": 453.35, "throughput_pps": 2.2, "cpu_util": 2.0, "gpu_util": 0.0},
        "gemma_1gpu": {"latency_ms": 3613.80, "throughput_pps": 0.30, "cpu_util": 14.2, "gpu_util": 98.5},
        "gemma_4gpu": {"latency_ms": 451.72, "throughput_pps": 2.20, "cpu_util": 38.0, "gpu_util": 99.2},
    },
    "routers": {
        "logistic_regression": {"latency_ms": 0.00014, "throughput_pps": 7142857.0, "cpu_util": 4.5, "gpu_util": 0.0},
        "random_forest": {"latency_ms": 0.00877, "throughput_pps": 114025.0, "cpu_util": 18.0, "gpu_util": 0.0},
        "vqc_aer": {"latency_ms": 10.889, "throughput_pps": 91.8, "cpu_util": 12.0, "gpu_util": 86.0},
    }
}

def generate_hardware_comparison(gh200_results_path: Path):
    """Generate comparative CSV and LaTeX outputs comparing GH200 vs MI250X."""
    if not gh200_results_path.exists():
        print(f"Results file {gh200_results_path} not found.")
        return

    with open(gh200_results_path, 'r') as f:
        gh200_data = json.load(f)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "data" / "reports" / f"gh200_comparison_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n========================================================================")
    print(f"=== HARDWARE COMPARISON: AMD MI250X vs NVIDIA GH200 GRACE HOPPER ===")
    print(f"Output Directory: {out_dir}")
    print(f"========================================================================\n")

    csv_path = out_dir / "mi250x_vs_gh200_comparison.csv"
    with open(csv_path, 'w') as f:
        f.write("Target,Architecture,MI250X_Latency_ms,GH200_Latency_ms,Latency_Improvement_x,MI250X_Throughput_pps,GH200_Throughput_pps,Throughput_Improvement_x,MI250X_GPU_Util,GH200_GPU_Util,GPU_Util_Diff\n")
        
        # Compare Reconcilers
        for rec, mi_m in MI250X_BASELINE["reconcilers"].items():
            gh_m = gh200_data.get("reconcilers", {}).get(rec, mi_m)
            lat_imp = mi_m["latency_ms"] / max(gh_m["latency_ms"], 1e-6)
            tp_imp = gh_m["throughput_pps"] / max(mi_m["throughput_pps"], 1e-6)
            gpu_diff = gh_m["gpu_util"] - mi_m["gpu_util"]
            f.write(f"{rec},Reconciler,{mi_m['latency_ms']},{gh_m['latency_ms']},{lat_imp:.2f},{mi_m['throughput_pps']},{gh_m['throughput_pps']},{tp_imp:.2f},{mi_m['gpu_util']},{gh_m['gpu_util']},{gpu_diff:+.1f}\n")

    print(f"✓ Summary CSV saved to: {csv_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GH200 Grace Hopper Benchmark Suite")
    parser.add_argument("--repetitions", type=int, default=10, help="Number of benchmark repetitions")
    parser.add_argument("--packets-file", type=str, default="data/ingested/telemetry_clean_bench_22500.json")
    args = parser.parse_args()

    # Detect hardware
    detector = HardwareDetector()
    hw = detector.detect()
    print(f"Detected Hardware Profile: {hw.get('model', 'Unknown')} ({hw.get('vram_gb', 0)}GB VRAM)")

    # Execute run_matrix
    sys.argv = [
        sys.argv[0],
        "--repetitions", str(args.repetitions),
        "--packets-file", args.packets_file,
        "--suffix", "gh200_spheron"
    ]
    run_matrix_main()
