#!/usr/bin/env python3
"""Deprecated compatibility entry point for the old clinical ingester."""

raise SystemExit(
    "scripts/ingest_openfda.py is deprecated because it allowed partial data "
    "and wrote the misleading source name 'clinical'. Use:\n\n"
    "  python scripts/pull_real_api_snapshot.py "
    "--sources openfda_adverse_events --packets-per-source 2500 "
    "--output data/ingested/openfda_adverse_events_2500_v1.json\n"
)
