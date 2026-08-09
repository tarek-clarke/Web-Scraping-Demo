from src.routing.canonical_vqc import (
    ABSTAIN_CLASS_INDEX,
    DEFAULT_CLASS_NAMES,
    counts_to_prediction,
)


def test_invalid_states_are_reported_and_can_abstain():
    decoded = counts_to_prediction({"110": 60, "001": 40})
    assert decoded["class_index"] == ABSTAIN_CLASS_INDEX
    assert decoded["class_name"] == "abstain"
    assert decoded["invalid_shots"] == 60
    assert decoded["invalid_state_rate"] == 0.6


def test_valid_state_wins_when_more_probable_than_aggregate_invalid_mass():
    decoded = counts_to_prediction({"010": 70, "111": 30})
    assert decoded["class_name"] == DEFAULT_CLASS_NAMES[2]
    assert decoded["abstain"] is False
