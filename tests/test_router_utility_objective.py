import numpy as np

from scripts.train_qpu_router import (
    acceptable_route_indices,
    classification_metrics,
    utility_loss,
)
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
    record = _record([1.0, 1.0, 0.96, 0.90, 0.80, 0.70])
    assert acceptable_route_indices(record) == [0, 1, 2]


def test_acceptable_routes_use_near_best_when_sla_is_unmet():
    record = _record([0.80, 0.79, 0.70, 0.60, 0.50, 0.40])
    assert acceptable_route_indices(record) == [0, 1]


def test_utility_loss_rewards_accurate_low_cost_routes():
    record = _record([1.0, 1.0, 0.70, 0.60, 0.50, 0.40])
    cheap = np.zeros((1, ROUTING_OUTPUT_SHAPE))
    cheap[0, 0] = 1.0
    inaccurate = np.zeros((1, ROUTING_OUTPUT_SHAPE))
    inaccurate[0, 5] = 1.0
    abstain = np.zeros((1, ROUTING_OUTPUT_SHAPE))
    abstain[0, -1] = 1.0
    assert utility_loss([record], cheap) < utility_loss([record], inaccurate)
    assert utility_loss([record], cheap) < utility_loss([record], abstain)


def test_metrics_distinguish_exact_label_from_acceptable_route():
    record = _record([1.0, 1.0, 0.70, 0.60, 0.50, 0.40])
    probabilities = np.zeros((1, ROUTING_OUTPUT_SHAPE))
    probabilities[0, 1] = 1.0
    metrics = classification_metrics(
        [record], np.asarray([1], dtype=int), probabilities
    )
    assert metrics["accuracy"] == 0.0
    assert metrics["acceptable_route_rate"] == 1.0
    assert metrics["mean_selected_reconciliation_accuracy"] == 1.0
    assert metrics["mean_accuracy_regret"] == 0.0
