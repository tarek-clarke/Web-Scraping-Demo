"""Schema-aware Stage-1 fast-path checks.

The routing benchmark is intended to send *schema* drift to the quantum
router.  Comparing complete packet values incorrectly treats normal telemetry
value changes (for example, a new speed or timestamp) as schema drift.  This
module provides a deterministic structural signature that ignores scalar
values while retaining keys, container shape, and scalar types.
"""

from __future__ import annotations

from typing import Any, Hashable, Tuple


def _scalar_type(value: Any) -> str:
    """Return a stable scalar type name without conflating bool and int."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, bytes):
        return "bytes"
    return type(value).__name__


def schema_signature(value: Any) -> Hashable:
    """Return a recursively comparable schema signature.

    Dictionary key order and scalar values are ignored.  Lists retain the set
    of element schemas they contain so that list/scalar and heterogeneous-list
    changes are detected without making the signature depend on list length.
    """
    if isinstance(value, dict):
        return (
            "dict",
            tuple(
                (str(key), schema_signature(child))
                for key, child in sorted(value.items(), key=lambda item: str(item[0]))
            ),
        )
    if isinstance(value, list):
        element_signatures = {
            repr(schema_signature(child)): schema_signature(child) for child in value
        }
        return (
            "list",
            tuple(element_signatures[key] for key in sorted(element_signatures)),
        )
    return ("scalar", _scalar_type(value))


def schemas_match(original_data: Any, candidate_data: Any) -> bool:
    """Return ``True`` when two payloads have the same structural schema."""
    return schema_signature(original_data) == schema_signature(candidate_data)


def packet_schemas_match(original_packet: dict, candidate_packet: dict) -> bool:
    """Compare only the ``data`` schemas of two telemetry packets."""
    return schemas_match(
        original_packet.get("data", {}),
        candidate_packet.get("data", {}),
    )


def schema_change_reason(original_data: Any, candidate_data: Any) -> Tuple[bool, str]:
    """Return a compact diagnostic describing whether Stage 2 is required."""
    original = schema_signature(original_data)
    candidate = schema_signature(candidate_data)
    if original == candidate:
        return False, "schema_match"
    return True, "schema_or_type_change"
