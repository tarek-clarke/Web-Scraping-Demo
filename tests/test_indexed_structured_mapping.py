from src.reconciliation.gemma_e4b_rec import GemmaE2BReconciler


def test_indexed_mapping_resolves_source_and_target_names():
    reconciler = GemmaE2BReconciler()
    mapped, unmapped, valid = reconciler._parse_index_mapping(
        "[1, null, 0]",
        {"lap_number": 1, "driver_name": "A", "sector_time": 2.3},
        {"sector_ms": 2300, "lap": 1},
    )
    assert valid is True
    assert mapped == [("lap_number", "lap"), ("sector_time", "sector_ms")]
    assert unmapped == ["driver_name"]


def test_indexed_mapping_rejects_placeholder_and_duplicate_targets():
    reconciler = GemmaE2BReconciler()
    original = {"a": 1, "b": 2}
    drifted = {"x": 1, "y": 2}
    for response in ('{"original":"drifted"}', "[0, 0]", "[0]"):
        mapped, unmapped, valid = reconciler._parse_index_mapping(
            response, original, drifted
        )
        assert valid is False
        assert mapped == []
        assert unmapped == ["a", "b"]
