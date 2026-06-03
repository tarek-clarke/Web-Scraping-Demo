#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== Resilient RAP Framework - Validation ===\n")

try:
    from src.hardware.detector import HardwareDetector
    print("✓ Hardware detector loaded")
except Exception as e:
    print(f"✗ Hardware detector: {e}")

try:
    from src.hardware.vram_prober import VRAMProber
    print("✓ VRAM prober loaded")
except Exception as e:
    print(f"✗ VRAM prober: {e}")

try:
    from src.chaos.injector import ChaosInjector
    print("✓ Chaos injector loaded")
except Exception as e:
    print(f"✗ Chaos injector: {e}")

try:
    from src.reconciliation.engine import ReconciliationEngine
    print("✓ Reconciliation engine loaded")
except Exception as e:
    print(f"✗ Reconciliation engine: {e}")

try:
    from src.orchestration.matrix_runner import MatrixRunner
    print("✓ Matrix runner loaded")
except Exception as e:
    print(f"✗ Matrix runner: {e}")

try:
    from src.telemetry.logger import TelemetryLogger
    print("✓ Telemetry logger loaded")
except Exception as e:
    print(f"✗ Telemetry logger: {e}")

print("\n=== Hardware Detection Test ===")
detector = HardwareDetector()
hw = detector.detect()
print(f"Detected: {hw['model']} ({hw['type']})")
print(f"VRAM: {hw['vram_gb']} GB")

print("\nValidation complete.")
