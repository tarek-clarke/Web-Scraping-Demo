#!/usr/bin/env python3
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hardware.detector import HardwareDetector
from src.hardware.vram_prober import VRAMProber
from src.orchestration.matrix_runner import MatrixRunner

def main():
    print("=== Resilient RAP Framework ===\n")
    
    detector = HardwareDetector()
    hardware = detector.detect()
    print(f"Detected Hardware: {hardware['model']}")
    print(f"Type: {hardware['type']}")
    print(f"VRAM: {hardware['vram_gb']} GB\n")
    
    prober = VRAMProber(hardware['type'])
    vram_info = prober.probe()
    print(f"Free VRAM: {vram_info['free_gb']:.2f} GB")
    print(f"Concurrent Runs: {vram_info['concurrent_runs']}")
    print(f"Batch Size: {vram_info['batch_size']}\n")
    
    packets_file = "data/ingested/telemetry_latest.json"
    if not os.path.exists(packets_file):
        print(f"Error: {packets_file} not found. Run Go ingestion first.")
        sys.exit(1)
    
    with open(packets_file, 'r') as f:
        packets = json.load(f)
    
    print(f"Loaded {len(packets)} packets\n")
    
    runner = MatrixRunner(
        hardware_profile=hardware['type'],
        concurrent_runs=vram_info['concurrent_runs'],
        batch_size=vram_info['batch_size']
    )
    
    print("Running matrix (60 combinations)...\n")
    results = runner.run(packets)
    
    print(f"\nCompleted {len(results['matrix'])} matrix runs")
    print(f"Results saved to data/reports/{hardware['type']}/")

if __name__ == "__main__":
    main()
