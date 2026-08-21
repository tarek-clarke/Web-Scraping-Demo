from scripts.build_qwen_chaos_snapshot import normalize_mapping


def test_duplicate_replacements_are_resolved_and_audited():
    original = {"date": 1, "session_key": 2, "meeting_key": 3}
    candidate = {
        "a": {"original_key": "date", "replacement_key": "event_id"},
        "b": {"original_key": "session_key", "replacement_key": "event_id"},
        "c": {"original_key": "meeting_key", "replacement_key": "meeting_id"},
    }

    mapping, repairs = normalize_mapping(original, candidate)

    assert mapping == {
        "date": "event_id",
        "session_key": "event_id_session_key",
        "meeting_key": "meeting_id",
    }
    assert repairs == [
        {
            "original_key": "session_key",
            "model_replacement": "event_id",
            "resolved_replacement": "event_id_session_key",
            "reason": "duplicate_replacement",
        }
    ]


def test_pure_key_permutation_is_forced_to_structural_drift():
    original = {"date": 1, "session_key": 2, "meeting_key": 3}

    mapping, repairs = normalize_mapping(
        original,
        {
            "date": "session_key",
            "session_key": "meeting_key",
            "meeting_key": "date",
        },
    )

    assert len(mapping) == len(original)
    assert len(set(mapping.values())) == len(original)
    assert set(mapping.values()) != set(original)
    assert repairs[0]["reason"] == "unchanged_output_schema"
