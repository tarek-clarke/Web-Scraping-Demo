from scripts.build_qwen_chaos_snapshot import normalize_mapping


def test_duplicate_replacements_are_resolved_and_audited():
    original = {"date": 1, "session_key": 2, "meeting_key": 3}
    candidate = {
        "a": {"original_key": "date", "replacement_key": "event_id"},
        "b": {"original_key": "session_key", "replacement_key": "event_id"},
        "c": {"original_key": "meeting_key", "replacement_key": "meeting_id"},
    }

    mapping, repairs, response_format = normalize_mapping(original, candidate)

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
    assert response_format == "nested_key_pairs"


def test_pure_key_permutation_is_forced_to_structural_drift():
    original = {"date": 1, "session_key": 2, "meeting_key": 3}

    mapping, repairs, response_format = normalize_mapping(
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
    assert response_format == "original_to_replacement"


def test_reverse_map_is_inverted_with_complete_coverage():
    original = {"date": 1, "session_key": 2, "meeting_key": 3}

    mapping, repairs, response_format = normalize_mapping(
        original,
        {
            "event_date": "date",
            "race_session_id": "session_key",
            "competition_id": "meeting_key",
        },
    )

    assert mapping == {
        "date": "event_date",
        "session_key": "race_session_id",
        "meeting_key": "competition_id",
    }
    assert repairs == []
    assert response_format == "replacement_to_original"


def test_one_decorated_reverse_value_is_recovered_and_audited():
    original = {
        "open_time": 1,
        "open": 2,
        "high": 3,
        "low": 4,
        "close": 5,
        "volume": 6,
        "quote_volume": 7,
        "trade_count": 8,
        "taker_buy_base": 9,
        "taker_buy_quote": 10,
    }

    mapping, repairs, response_format = normalize_mapping(
        original,
        {
            "timestamp": "open_time_ms",
            "symbol": "open",
            "highestBid": "high",
            "lowestAsk": "low",
            "lastTradePrice": "close",
            "totalTradedVolume": "volume",
            "totalQuoteVolume": "quote_volume",
            "numberOfTrades": "trade_count",
            "makerFeeAmount": "taker_buy_base",
            "makerFeeRate": "taker_buy_quote",
        },
    )

    assert mapping["open_time"] == "timestamp"
    assert len(mapping) == len(original)
    assert len(set(mapping.values())) == len(original)
    assert repairs == [
        {
            "original_key": "open_time",
            "reported_original_key": "open_time_ms",
            "replacement_key": "timestamp",
            "reason": "reverse_original_key_recovered_by_elimination",
        }
    ]
    assert response_format == "replacement_to_original_repaired"


def test_multiple_decorated_reverse_values_fail_loudly():
    original = {"open_time": 1, "open": 2, "high": 3}

    try:
        normalize_mapping(
            original,
            {
                "timestamp": "open_time_ms",
                "openingPrice": "open_price",
                "highestBid": "high",
            },
        )
    except ValueError as exc:
        assert "not a complete reverse" in str(exc)
    else:
        raise AssertionError("ambiguous reverse map should fail loudly")
