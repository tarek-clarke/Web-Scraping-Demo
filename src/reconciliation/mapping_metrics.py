"""Ground-truth field decisions and method-independent reconciliation metrics."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, Mapping, Sequence


_KNOWN_RENAMES = {
    "temperature": {"temp_c"},
    "speed": {"velocity", "velocity_kmh"},
    "price": {"cost"},
    "timestamp": {"ts", "timestamp_utc"},
    "driver_number": {"driver_id"},
    "rpm": {"engine_rotations"},
    "gear": {"selected_gear"},
    "throttle": {"gas_pedal_pct"},
    "brake": {"brake_pressure_pct"},
    "drs": {"drs_status"},
    "date": {"timestamp_utc"},
    "session_key": {"meeting_session_id"},
    "meeting_key": {"event_id"},
}


def _dict(value: object) -> Dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    if isinstance(value, list):
        return {str(index): item for index, item in enumerate(value)}
    return {}


def _normalise_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _same_value(left: object, right: object) -> bool:
    try:
        return json.dumps(left, sort_keys=True, default=str) == json.dumps(
            right, sort_keys=True, default=str
        )
    except Exception:
        return left == right


def _candidate_score(source: str, value: object, target: str, target_value: object) -> float:
    source_norm, target_norm = _normalise_key(source), _normalise_key(target)
    score = SequenceMatcher(None, source_norm, target_norm).ratio()
    if source_norm == target_norm:
        score += 4.0
    if target in _KNOWN_RENAMES.get(source, set()):
        score += 4.0
    if source_norm and source_norm in target_norm:
        score += 2.0
    if _same_value(value, target_value):
        score += 3.0
    if isinstance(target_value, dict) and source in target_value:
        score += 3.5
    if isinstance(target_value, str) and str(value) in target_value:
        score += 1.5
    return score


def derive_ground_truth_mapping(
    original: object,
    drifted: object,
) -> Dict[str, str | None]:
    """Derive the injected top-level source decision for every original field.

    A ``None`` target is an intentional dropped/unrecoverable field.  The chaos
    transformations are deterministic and preserve either the key, its known
    renamed form, its value, or its containing structural key; those signals
    provide a reproducible provenance decision without using model output.
    """
    sources, targets = _dict(original), _dict(drifted)
    truth: Dict[str, str | None] = {}
    for source, value in sources.items():
        if source in targets:
            truth[source] = source
            continue
        ranked = sorted(
            (
                (_candidate_score(source, value, target, target_value), target)
                for target, target_value in targets.items()
            ),
            reverse=True,
        )
        truth[source] = ranked[0][1] if ranked and ranked[0][0] >= 3.0 else None
    return truth


def normalise_predicted_mapping(
    mapped_fields: object,
    unmapped_fields: Iterable[object] = (),
) -> Dict[str, str | None]:
    predicted: Dict[str, str | None] = {}
    items = mapped_fields.items() if isinstance(mapped_fields, Mapping) else mapped_fields or ()
    for item in items:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            predicted[str(item[0])] = str(item[1])
    for source in unmapped_fields or ():
        predicted.setdefault(str(source), None)
    return predicted


def exact_mapping_metrics(
    truth: Mapping[str, str | None],
    mapped_fields: object,
    unmapped_fields: Sequence[object] = (),
) -> Dict[str, float | int]:
    """Score exact field decisions with one definition for every method."""
    predicted = normalise_predicted_mapping(mapped_fields, unmapped_fields)
    sources = list(truth)
    correct = sum(predicted.get(source) == truth[source] for source in sources)
    expected_pairs = {(source, target) for source, target in truth.items() if target is not None}
    predicted_pairs = {
        (source, target)
        for source, target in predicted.items()
        if target is not None and source in truth
    }
    true_positive = len(expected_pairs & predicted_pairs)
    precision = true_positive / len(predicted_pairs) if predicted_pairs else float(not expected_pairs)
    recall = true_positive / len(expected_pairs) if expected_pairs else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": correct / len(sources) if sources else 1.0,
        "exact_record_match": int(correct == len(sources)),
        "mapping_precision": precision,
        "mapping_recall": recall,
        "mapping_f1": f1,
        "correct_field_decisions": correct,
        "field_decisions": len(sources),
    }
