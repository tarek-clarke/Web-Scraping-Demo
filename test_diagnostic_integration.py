#!/usr/bin/env python3
"""
Quick integration test for diagnostic framework
Verifies: SensorCadenceMonitor, DiagnosticFaultTracker, and diagnostic flag parsing
"""

import sys
from pathlib import Path

# Add repo to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

def test_imports():
    """Test that all components can be imported."""
    try:
        from src.circuit_breaker import SensorCadenceMonitor
        print("✅ SensorCadenceMonitor imported successfully")
        
        # Try to instantiate
        monitor = SensorCadenceMonitor(history_size=100, cadence_tolerance=3.0)
        print("✅ SensorCadenceMonitor instantiated successfully")
        
        # Test reset method
        monitor.reset()
        print("✅ SensorCadenceMonitor.reset() works")
        
    except Exception as e:
        print(f"❌ SensorCadenceMonitor import failed: {e}")
        return False

    try:
        from tools.telemetry_gpu_stress_test import DiagnosticFaultTracker
        print("✅ DiagnosticFaultTracker imported successfully")
        
        # Try to instantiate
        tracker = DiagnosticFaultTracker(capacity=1000)
        print("✅ DiagnosticFaultTracker instantiated successfully")
        
        # Try to build empty analysis
        analysis = tracker.build_analysis()
        print(f"✅ DiagnosticFaultTracker.build_analysis() works → {len(analysis)} keys")
        
    except Exception as e:
        print(f"❌ DiagnosticFaultTracker import failed: {e}")
        return False

    try:
        from tools.sensor_fault_diagnostic import SensorFaultDiagnostic
        print("✅ SensorFaultDiagnostic imported successfully")
        
        # Try to instantiate with empty analysis
        test_analysis = {
            "missed_fault_count": 0,
            "detection_rate": 1.0,
            "miss_rate": 0.0,
            "missed_by_sensor": [],
            "missed_by_chaos_mode": [],
            "missed_by_session": [],
            "missed_by_sensor_and_chaos": [],
        }
        diag = SensorFaultDiagnostic(test_analysis)
        print("✅ SensorFaultDiagnostic instantiated successfully")
        
    except Exception as e:
        print(f"❌ SensorFaultDiagnostic import failed: {e}")
        return False

    return True


def test_argparse():
    """Test that --diagnostic flag is recognized."""
    try:
        import argparse
        from tools.telemetry_gpu_stress_test import main
        
        # Verify that --diagnostic appears in the stress test's argument parser
        # Can't easily test argparse without running main, but we can check the help text
        print("✅ Diagnostic integration test: checking for --diagnostic flag...")
        
        # Read the file to verify the flag is in there
        stress_test_path = Path(__file__).parent / "tools" / "telemetry_gpu_stress_test.py"
        content = stress_test_path.read_text()
        
        if '"--diagnostic"' in content and 'action="store_true"' in content:
            print("✅ --diagnostic flag found in argparse configuration")
        else:
            print("❌ --diagnostic flag not found in argparse configuration")
            return False
            
        if "self.diagnostic = diagnostic" in content:
            print("✅ diagnostic parameter passed to TelemetryGPUStressTest.__init__")
        else:
            print("❌ diagnostic parameter not found in __init__")
            return False
            
    except Exception as e:
        print(f"❌ Argparse test failed: {e}")
        return False

    return True


def test_exports():
    """Test that export functions reference missed_detection_analysis."""
    try:
        stress_test_path = Path(__file__).parent / "tools" / "telemetry_gpu_stress_test.py"
        content = stress_test_path.read_text()
        
        if "missed_detection_analysis" in content:
            count = content.count("missed_detection_analysis")
            print(f"✅ 'missed_detection_analysis' found {count} times in stress test")
        else:
            print("❌ 'missed_detection_analysis' not found in stress test")
            return False
            
        if "missed_detection_analysis{self.output_suffix}.json" in content:
            print("✅ JSON export path found")
        else:
            print("❌ JSON export path not found")
            return False
            
        if "missed_detection_analysis{self.output_suffix}.csv" in content:
            print("✅ CSV export path found")
        else:
            print("❌ CSV export path not found")
            return False
            
    except Exception as e:
        print(f"❌ Export test failed: {e}")
        return False

    return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("GPU STRESS TEST DIAGNOSTIC FRAMEWORK - INTEGRATION TEST")
    print("=" * 70 + "\n")

    print("[1/3] Testing Imports...")
    imports_ok = test_imports()

    print("\n[2/3] Testing Argparse Integration...")
    argparse_ok = test_argparse()

    print("\n[3/3] Testing Export Integration...")
    exports_ok = test_exports()

    print("\n" + "=" * 70)
    if imports_ok and argparse_ok and exports_ok:
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("=" * 70 + "\n")
        sys.exit(0)
    else:
        print("❌ SOME INTEGRATION TESTS FAILED")
        print("=" * 70 + "\n")
        sys.exit(1)
