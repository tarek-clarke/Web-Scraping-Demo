#!/usr/bin/env python3
import json
import sys
import os
import time as time_mod
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.hardware.detector import HardwareDetector
from src.hardware.vram_prober import VRAMProber
from src.orchestration.matrix_runner import MatrixRunner

def main():
    parser = argparse.ArgumentParser(description="Resilient RAP Framework")
    parser.add_argument("--repetitions", type=int, default=3, help="Iterations per combination (default: 3)")
    args = parser.parse_args()

    run_start = time_mod.time()

    print("=== Resilient RAP Framework ===\n")

    detector = HardwareDetector()
    hardware = detector.detect()

    prober = VRAMProber(hardware['type'])
    vram_info = prober.probe()

    print(f"GPU Model: {hardware['model']}")
    print(f"Hardware Type: {hardware['type']}")
    print(f"CPU: {hardware.get('cpu', 'N/A')}")
    print(f"Motherboard: {hardware.get('motherboard', 'N/A')}")
    print(f"Total VRAM: {hardware['vram_gb']} GB")
    print(f"Free VRAM: {vram_info['free_gb']:.2f} GB")
    print(f"Driver: {hardware.get('driver', 'N/A')}")
    print(f"OS: {hardware['os']}")
    print(f"Concurrent Runs: {vram_info['concurrent_runs']}")
    print(f"Batch Size: {vram_info['batch_size']}")
    print(f"Iterations: {args.repetitions}\n")

    packets_file = "data/ingested/telemetry_latest.json"
    if not os.path.exists(packets_file):
        print(f"Error: {packets_file} not found. Run Go ingestion first.")
        sys.exit(1)

    with open(packets_file, 'r') as f:
        packets = json.load(f)

    print(f"Loaded {len(packets)} packets\n")

    runner = MatrixRunner(
        hardware_profile=hardware,
        concurrent_runs=vram_info['concurrent_runs'],
        batch_size=vram_info['batch_size'],
        repetitions=args.repetitions
    )

    total_runs = len(runner.apis) * len(runner.chaos_methods) * 5 * args.repetitions
    print(f"Running {total_runs} matrix runs ({4} APIs x {3} chaos x 5 reconcilers x {args.repetitions} iterations)...\n")

    results = runner.run(packets)

    results["run_metadata"] = {
        "start_time": run_start,
        "end_time": time_mod.time(),
        "total_duration_s": time_mod.time() - run_start,
        "total_packets": len(packets),
        "hardware": {
            "model": hardware.get("model", "unknown"),
            "type": hardware.get("type", "unknown"),
            "cpu": hardware.get("cpu", "unknown"),
            "motherboard": hardware.get("motherboard", "unknown"),
            "vram_gb": hardware.get("vram_gb", 0),
            "free_vram_gb": round(vram_info.get("free_gb", 0), 2),
            "driver": hardware.get("driver", "unknown"),
            "os": hardware.get("os", "unknown"),
            "python_version": hardware.get("python_version", "unknown"),
            "concurrent_runs": vram_info.get("concurrent_runs", 1),
            "batch_size": vram_info.get("batch_size", 1)
        },
        "cite_method": "Hosseini et al. (2016) - Quantitative Resilience Index: AUC / baseline_perf * t_total",
        "method_reference": "Hosseini, S., Barker, K., & Ramirez-Marquez, J.E. (2016). A review of definitions and measures of system resilience. Reliability Engineering & System Safety, 145, 47-61."
    }

    print(f"\nCompleted {len(results['matrix'])} aggregated combinations ({len(results['iterations'])} total iterations)")
    print(f"Duration: {results['run_metadata']['total_duration_s']:.0f}s")
    print(f"Results saved to data/reports/{hardware['type']}/")

if __name__ == "__main__":
    main()
