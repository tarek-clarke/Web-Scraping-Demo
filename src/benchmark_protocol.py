"""Versioned constants for the publication benchmark.

The v9 protocol replaces the deprecated repeated/synthetic records with an
immutable snapshot of 2,500 distinct records from each of nine public APIs.
"""

from __future__ import annotations

SNAPSHOT_SCHEMA_VERSION = 1
PACKETS_PER_SOURCE = 2_500

ACTIVE_API_SOURCES = (
    "openf1",
    "binance_market",
    "noaa_space_weather",
    "openmeteo_weather",
    "openfda_adverse_events",
    "hockey_nhl",
    "aviation_opensky",
    "football_openligadb",
    "smartcity_mbta",
)

SOURCE_ENCODING = {
    source: (index + 1) / 10.0
    for index, source in enumerate(ACTIVE_API_SOURCES)
}

DEFAULT_SNAPSHOT_PATH = "data/ingested/telemetry_real_api_22500_v1.json"
DEFAULT_SNAPSHOT_MANIFEST = "data/ingested/telemetry_real_api_22500_v1.manifest.json"
