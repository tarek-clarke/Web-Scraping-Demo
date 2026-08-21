import numpy as np

from scripts.train_qpu_router import (
    acceptable_route_indices,
    blended_metrics,
    classification_metrics,
    select_maximum_qpu_weight,
    utility_loss,
)
from scripts.run_qpu_router_experiment import enrich_prediction
from src.routing.canonical_vqc import DEFAULT_CLASS_NAMES, ROUTING_OUTPUT_SHAPE


def _record(accuracies, oracle_method="levenshtein"):
    return {
        "oracle_label": DEFAULT_CLASS_NAMES.index(oracle_method),
        "oracle_method": oracle_method,
        "method_metrics": {
            method: {"accuracy": accuracy, "latency_ms": index + 1.0}
            for index, (method, accuracy) in enumerate(
                zip(DEFAULT_CLASS_NAMES, accuracies)
            )
        },
    }


def test_acceptable_routes_include_all_methods_meeting_sla():
    record = _record([1.0, 1.0, 0.96, 0.90, 0.80, 0.70, 0.60, 0.50])
    assert acceptable_route_indices(record) == [0, 1, 2]


def test_acceptable_routes_use_near_best_when_sla_is_unmet():
    record = _record([0.80, 0.79, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20])
    assert acceptable_route_indices(record) == [0, 1]


def test_utility_loss_rewards_accurate_low_cost_routes():
    record = _record([1.0, 1.0, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20])
    cheap = np.zeros((1, ROUTING_OUTPUT_SHAPE))
    cheap[0, 0] = 1.0
    inaccurate = np.zeros((1, ROUTING_OUTPUT_SHAPE))
    inaccurate[0, 5] = 1.0
    assert utility_loss([record], cheap) < utility_loss([record], inaccurate)


def test_metrics_distinguish_exact_label_from_acceptable_route():
    record = _record([1.0, 1.0, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20])
    probabilities = np.zeros((1, ROUTING_OUTPUT_SHAPE))
    probabilities[0, 1] = 1.0
    metrics = classification_metrics(
        [record], np.asarray([1], dtype=int), probabilities
    )
    assert metrics["accuracy"] == 0.0
    assert metrics["acceptable_route_rate"] == 1.0
    assert metrics["mean_selected_reconciliation_accuracy"] == 1.0
    assert metrics["mean_accuracy_regret"] == 0.0


def test_hybrid_calibration_selects_largest_safe_qpu_weight():
    records = [
        _record([1.0, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0, 0.0]),
        _record([1.0, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0, 0.0]),
    ]
    qpu = np.zeros((2, ROUTING_OUTPUT_SHAPE))
    qpu[:, 1] = 1.0
    classical = np.zeros((2, ROUTING_OUTPUT_SHAPE))
    classical[:, 0] = 1.0
    weight, metrics = select_maximum_qpu_weight(
        records,
        qpu,
        classical,
        accuracy_sla=0.95,
        accuracy_tolerance=0.01,
        min_reconciliation_accuracy=0.90,
        max_accuracy_regret=0.05,
        min_acceptable_route_rate=0.80,
    )
    assert 0.49 <= weight <= 0.5
    assert metrics["mean_selected_reconciliation_accuracy"] == 1.0
    recomputed, _ = blended_metrics(
        records,
        qpu,
        classical,
        weight,
        accuracy_sla=0.95,
        accuracy_tolerance=0.01,
    )
    assert recomputed["acceptable_route_rate"] == 1.0


def test_physical_counts_use_frozen_hybrid_weight_transparently():
    record = {
        **_record([1.0, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0, 0.0]),
        "record_id": "example",
        "api": "openf1",
        "packet_index": 1,
        "chaos_method": "qwen",
        "chaos_subtype": "rename",
        "features": [0.0] * 10,
    }
    decoded = {
        "class_name": "regex",
        "class_index": 1,
        "probabilities": [0.1, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "invalid_state_rate": 0.0,
        "confidence": 0.9,
        "abstain": False,
        "invalid_shots": 0,
        "shots": 100,
    }
    classical = np.zeros(ROUTING_OUTPUT_SHAPE)
    classical[0] = 1.0
    row = enrich_prediction(
        record,
        decoded,
        repetition="1",
        counts={"001": 90, "000": 10},
        classical_probabilities=classical,
        qpu_weight=0.5,
    )
    assert row["qpu_selected_method"] == "regex"
    assert row["selected_method"] == "levenshtein"
    assert row["qpu_weight"] == 0.5
