import pytest
import os
import tempfile
import numpy as np
from unittest.mock import MagicMock, patch
from src.telemetry.metrics_logger import EnergyTracker
from src.reconciliation.engine import ReconciliationEngine
from src.routing.quantum_router import QuantumRouter

def test_energy_tracker_calculations():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "energy_profile.csv")
        tracker = EnergyTracker(output_path=csv_path)
        tracker.start()
        
        # Manually assign active joules for testing
        tracker.cpu_joules = 100.0
        tracker.gpu_joules = 400.0
        
        metrics = tracker.get_metrics()
        assert metrics["cpu_energy_draw_joules"] == pytest.approx(100.0, rel=1e-2)
        assert metrics["gpu_energy_draw_joules"] == pytest.approx(400.0, rel=1e-2)
        assert metrics["cumulative_kwh"] > 0
        
        # Test carbon offset (1 drifted packet baseline gemma = 120 Joules)
        # With 10 drifted packets, baseline = 1200 Joules. Saved = 700 Joules
        # Saved kWh = 700 / 3.6e6
        offset = tracker.calculate_carbon_offset_mg(total_drifted_packets=10)
        assert offset > 0.0

def test_engine_route_and_reconcile():
    engine = ReconciliationEngine(hardware_profile="cpu", batch_size=4)
    
    # Mock router and feature extractor
    mock_router = MagicMock()
    mock_router.route_packet.return_value = ("levenshtein", 0.95)
    mock_router.last_telemetry = {
        "qpu_execution_time_ms": 12.34,
        "classical_simulation_baseline_ms": 0.0,
        "quantum_loop_iterations": 1,
        "gate_fidelity_average": 0.992,
        "qubit_coherence_status_score": 0.985
    }
    
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = np.zeros(10)
    
    original = {"data": {"field_a": "value"}, "source": "test_api"}
    drifted = {"data": {"field_a": "value"}, "source": "test_api"}
    
    result = engine.route_and_reconcile(original, drifted, mock_router, mock_extractor)
    
    assert result["routing_decision"] == "levenshtein"
    assert result["optimal_reconciler"] == "levenshtein"
    assert result["routing_decision_match"] is True
    assert result["qpu_execution_time_ms"] == 12.34
    assert result["gate_fidelity_average"] == 0.992
