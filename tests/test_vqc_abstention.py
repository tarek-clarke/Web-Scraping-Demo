from src.routing.canonical_vqc import (
    ABSTAIN_CLASS_INDEX,
    DEFAULT_CLASS_NAMES,
    counts_to_prediction,
)


def test_invalid_states_are_reported_and_can_abstain():
    decoded = counts_to_prediction({"110": 60, "001": 40}, confidence_threshold=0.70)
    assert decoded["class_index"] == ABSTAIN_CLASS_INDEX
    assert decoded["class_name"] == "abstain"
    assert decoded["invalid_shots"] == 0
    assert decoded["invalid_state_rate"] == 0.0


def test_every_state_is_a_valid_route_without_threshold():
    decoded = counts_to_prediction({"010": 70, "111": 30})
    assert decoded["class_name"] == DEFAULT_CLASS_NAMES[2]
    assert decoded["abstain"] is False
