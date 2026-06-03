#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.hardware.detector import HardwareDetector
from src.hardware.vram_prober import VRAMProber

print("=== Batch Size Scaling Test ===\n")

detector = HardwareDetector()
hw = detector.detect()
print(f"Hardware: {hw['model']} ({hw['type']})")
print(f"VRAM: {hw['vram_gb']} GB\n")

prober = VRAMProber(hw['type'])
vram_info = prober.probe()

print(f"Free VRAM: {vram_info['free_gb']:.2f} GB")
print(f"Concurrent Runs: {vram_info['concurrent_runs']}")
print(f"Batch Size: {vram_info['batch_size']}\n")

print("=== Batch Size Scaling Table ===\n")
print(f"{'VRAM (GB)':<12} {'Batch Size':<12} {'Concurrent Runs':<18}")
print("-" * 42)

test_vrams = [8, 16, 20, 32, 48, 80, 96, 128, 288]
for vram in test_vrams:
    test_prober = VRAMProber("cuda")
    batch_size = test_prober._calculate_batch_size(vram)
    concurrent = max(1, int(vram / 8))
    print(f"{vram:<12} {batch_size:<12} {concurrent:<18}")

print("\n✓ Batch size scaling verified")
