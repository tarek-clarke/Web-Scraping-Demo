from scripts.build_v9_replay import inject_rule
from src.routing.schema_fast_path import schemas_match


def test_schema_alter_falls_back_when_random_subtype_is_structurally_inert():
    original = {"value": "unchanged", "status": "ok"}

    subtype, drifted = inject_rule(original, "schema_alter", 7)

    assert not schemas_match(original, drifted)
    assert subtype


def test_json_manip_falls_back_when_random_subtype_is_structurally_inert():
    original = {"value": "unchanged", "status": "ok"}

    subtype, drifted = inject_rule(original, "json_manip", 13)

    assert not schemas_match(original, drifted)
    assert subtype
