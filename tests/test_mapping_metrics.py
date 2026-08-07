from src.reconciliation.mapping_metrics import (
    derive_ground_truth_mapping,
    exact_mapping_metrics,
)


def test_exact_mapping_uses_injected_target_and_dropped_decision():
    original = {"speed": 100, "driver_number": 4, "obsolete": True}
    drifted = {"velocity": 100, "driver_id": 4}
    truth = derive_ground_truth_mapping(original, drifted)
    assert truth == {
        "speed": "velocity",
        "driver_number": "driver_id",
        "obsolete": None,
    }
    metrics = exact_mapping_metrics(
        truth,
        [("speed", "velocity"), ("driver_number", "driver_id")],
        ["obsolete"],
    )
    assert metrics["accuracy"] == 1.0
    assert metrics["exact_record_match"] == 1


def test_wrong_mapping_is_not_rewarded_for_coverage():
    truth = {"speed": "velocity", "timestamp": "ts"}
    metrics = exact_mapping_metrics(
        truth,
        [("speed", "ts"), ("timestamp", "velocity")],
        [],
    )
    assert metrics["accuracy"] == 0.0
    assert metrics["mapping_f1"] == 0.0

