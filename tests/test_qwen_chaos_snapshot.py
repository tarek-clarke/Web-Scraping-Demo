from scripts.build_qwen_chaos_snapshot import normalize_mapping, salvage_partial_mapping


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


def test_partial_reverse_mapping_keeps_only_exact_pairs_and_is_audited():
    original = {
        "safetyreportid": 1,
        "transmissiondateformat": 2,
        "transmissiondate": 3,
        "serious": 4,
        "receivedateformat": 5,
        "receivedate": 6,
        "receiptdateformat": 7,
        "receiptdate": 8,
        "fulfillexpeditecriteria": 9,
        "companynumb": 10,
        "primarysource": 11,
        "sender": 12,
        "receiver": 13,
        "patient": 14,
    }
    candidate = {
        "safety_report_id": "transmission_date_format",
        "transmission_date": "transmission_date",
        "serious": "receivedate_format",
        "receivedate": "receivedate",
        "receipt_date": "receiptdate",
        "receipt_date_format": "receiptdate_format",
        "fulfill_expedite_criteria": "companynumber",
        "company_number": "companynumb",
        "primary_source": "sender",
        "primary_source_format": "sender",
        "sender": "receiver",
        "sender_format": "receiver",
        "patient": "patient",
    }

    mapping, repairs, response_format = salvage_partial_mapping(original, candidate)

    assert mapping["receiptdate"] == "receipt_date"
    assert mapping["companynumb"] == "company_number"
    assert mapping["safetyreportid"] == "safetyreportid"
    assert mapping["sender"] == "sender"
    assert len(mapping) == len(original)
    assert len(set(mapping.values())) == len(original)
    assert response_format == "replacement_to_original_partial"
    assert any(repair["original_key"] == "safetyreportid" for repair in repairs)


def test_partial_mapping_with_no_exact_evidence_fails_loudly():
    original = {"date": 1, "session_key": 2, "meeting_key": 3}

    try:
        salvage_partial_mapping(
            original,
            {
                "driving_style": "style",
                "engine_rpm_range": "rpm_range",
                "pit_stop_count": "stop_count",
            },
        )
    except ValueError as exc:
        assert "zero exact coverage" in str(exc)
    else:
        raise AssertionError("unrelated mapping should fail loudly")


def test_partial_direct_mapping_preserves_omitted_originals():
    original = {"date": 1, "session_key": 2, "meeting_key": 3}

    mapping, repairs, response_format = salvage_partial_mapping(
        original,
        {
            "date": "event_date",
            "session_key": "race_session_id",
            "unrelated_extra": "ignore_me",
        },
    )

    assert mapping == {
        "date": "event_date",
        "session_key": "race_session_id",
        "meeting_key": "meeting_key",
    }
    assert repairs == [
        {
            "original_key": "meeting_key",
            "model_replacement": "",
            "resolved_replacement": "meeting_key",
            "reason": "partial_direct_original_preserved",
        }
    ]
    assert response_format == "original_to_replacement_partial"


def test_partial_camel_case_openfda_response_uses_canonical_names():
    original = {
        "safetyreportid": 1,
        "transmissiondateformat": 2,
        "transmissiondate": 3,
        "serious": 4,
        "seriousnessdeath": 5,
        "receivedateformat": 6,
        "receivedate": 7,
        "receiptdateformat": 8,
        "receiptdate": 9,
        "fulfillexpeditecriteria": 10,
        "companynumb": 11,
        "primarysource": 12,
        "sender": 13,
        "receiver": 14,
        "patient": 15,
    }
    candidate = {
        "safety_report_id": "safetyReportId",
        "transmission_date_format": "transmissionDateFormat",
        "transmission_date": "transmissionDate",
        "serious": "seriousnessDeath",
        "seriousness_death": "seriousnessDeath",
        "receivedate_format": "receivedateFormat",
        "receivedate": "receivedate",
        "receipt_date_format": "receiptdateFormat",
        "receiptdate": "receiptdate",
        "fulfill_expedite_criteria": "fulfillexpediteCriteria",
        "company_numb": "companynumb",
        "primary_source": "primarySource",
        "sender": "sender",
        "sender_format": "sender",
        "receiver": "receiver",
        "receiver_format": "receiver",
        "patient": "patient",
    }

    mapping, repairs, response_format = salvage_partial_mapping(original, candidate)

    assert mapping["safetyreportid"] == "safety_report_id"
    assert mapping["transmissiondate"] == "transmission_date"
    assert mapping["companynumb"] == "company_numb"
    assert mapping["seriousnessdeath"] == "seriousnessdeath"
    assert len(mapping) == len(original)
    assert len(set(mapping.values())) == len(original)
    assert response_format == "replacement_to_original_partial"
    assert any("partial_reverse" in repair["reason"] for repair in repairs)


def test_equal_canonical_coverage_follows_direct_contract():
    original = {
        "safetyreportid": 1,
        "transmissiondateformat": 2,
        "transmissiondate": 3,
        "serious": 4,
        "seriousnessdeath": 5,
        "receivedateformat": 6,
        "receivedate": 7,
        "receiptdateformat": 8,
        "receiptdate": 9,
        "fulfillexpeditecriteria": 10,
        "companynumb": 11,
        "primarysource": 12,
        "sender": 13,
        "receiver": 14,
        "patient": 15,
    }
    candidate = {
        "safety_report_id": "transmission_date_format",
        "transmission_date_format": "transmission_date",
        "transmission_date": "seriousness_death",
        "serious": "receivedate_format",
        "seriousness_death": "receivedate",
        "receivedate": "fulfillexpedite_criteria",
        "receivedate_format": "company_numb",
        "fulfillexpedite_criteria": "primary_source",
        "company_numb": "sender",
        "primary_source": "receiver",
        "sender": "patient",
    }

    mapping, repairs, response_format = salvage_partial_mapping(original, candidate)

    assert mapping["safetyreportid"] == "transmission_date_format"
    assert mapping["transmissiondateformat"] == "transmission_date"
    assert response_format == "original_to_replacement_partial"
    assert any(
        repair["reason"] == "partial_orientation_contract_tiebreak_direct"
        for repair in repairs
    )
