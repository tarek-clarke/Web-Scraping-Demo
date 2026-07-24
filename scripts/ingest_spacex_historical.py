#!/usr/bin/env python3
"""
SpaceX Historical Data Ingestion Script

Fetches historical SpaceX launch data for testing the Resilient RAP Framework.

Usage:
    python3 scripts/ingest_spacex_historical.py

Output:
    data/ingested/spacex_launches.json (2,500 packets)
"""

import json
import time
import random
from datetime import datetime, timedelta
from collections import defaultdict

import requests

OUTPUT_FILE = "data/ingested/spacex_launches.json"
TARGET_PACKETS = 2500


def get_spacex_launches():
    """Fetch recent SpaceX launches."""
    url = "https://api.spacexdata.com/v5/launches/query"
    payload = {
        "query": {},
        "options": {"limit": 50, "sort": {"date_utc": "desc"}}
    }
    resp = requests.post(url, json=payload, timeout=10)
    if resp.status_code != 200:
        return []
    data = resp.json()
    if isinstance(data, dict) and "docs" in data:
        return data["docs"]
    return []


def generate_spacex_telemetry(launch, timestamp):
    """Generate SpaceX telemetry packet."""
    rocket = launch.get("rocket", "Unknown")
    name = launch.get("name", "Unknown Launch")
    date = launch.get("date_utc", "")
    success = launch.get("success")
    failures = launch.get("failures", [])
    payloads = launch.get("payloads", [])

    payload_ids = []
    payload_mass = 0
    payload_types = set()
    for p in payloads:
        if isinstance(p, dict):
            payload_ids.append(p.get("id", ""))
            payload_mass += p.get("mass_kg", 0)
            pt = p.get("type", "Unknown")
            if pt:
                payload_types.add(pt)
        elif isinstance(p, str):
            payload_ids.append(p)

    return {
        "source": "spacex",
        "timestamp": timestamp.isoformat(),
        "data": {
            "mission_name": name,
            "launch_date_utc": date,
            "rocket_id": rocket,
            "launch_success": success if success is not None else False,
            "upcoming": launch.get("upcoming", False),
            "static_fire_date_utc": launch.get("static_fire_date_utc"),
            "net_duration": launch.get("net", ""),
            "window_start": launch.get("window_start_utc"),
            "window_end": launch.get("window_end_utc"),
            "failure_count": len(failures),
            "failure_reasons": [f.get("reason", "") if isinstance(f, dict) else str(f) for f in failures],
            "payload_count": len(payloads),
            "payload_ids": payload_ids,
            "payload_mass_kg": payload_mass,
            "payload_type": ", ".join(payload_types) if payload_types else "Unknown",
            "crew_count": len(launch.get("crew", [])),
            "launch_site": launch.get("launchpad", "Unknown"),
            "auto_payload": launch.get("auto_update", False),
            "tbd": launch.get("tbd", False),
            "gridfins": launch.get("gridfins", False),
            "legs": launch.get("legs", False),
            "reused": launch.get("reused", False),
            "fairings_reused": launch.get("fairings_reused", False),
            "fairings_recovery_attempt": launch.get("fairings_recovery_attempt", False),
            "cores_reused": launch.get("cores_reused", False),
            "ships": launch.get("ships", []),
            "capsules": launch.get("capsules", []),
            "flight_number": launch.get("flight_number", 0),
        }
    }


def collect_spacex(target_packets):
    """Collect SpaceX telemetry."""
    print("Fetching SpaceX launches...")
    launches = get_spacex_launches()

    if not launches:
        print("No launches found, using fallback data")
        return collect_fallback(target_packets)

    print(f"Found {len(launches)} launches")

    packets = []
    start_time = datetime.utcnow()

    for i in range(target_packets):
        launch = random.choice(launches)
        ts = start_time + timedelta(seconds=i * 0.5)
        packets.append(generate_spacex_telemetry(launch, ts))

        if (i + 1) % 500 == 0:
            print(f"  Progress: {i + 1}/{target_packets}")

    return packets


def collect_fallback(target_packets):
    """Fallback mock data."""
    print(f"Generating {target_packets} mock SpaceX telemetry packets...")

    launches = [
        {"name": "Starlink Group 6-1", "rocket": "5e9e1502f499c70000000001", "date_utc": "2026-05-24T00:00:00Z", "success": True, "failures": [], "payloads": [{"id": "starlink-200", "type": "Satellite", "mass_kg": 650}], "flight_number": 300},
        {"name": "Crew-10", "rocket": "5e9e1502f499c70000000002", "date_utc": "2026-03-15T00:00:00Z", "success": True, "failures": [], "payloads": [{"id": "crew-dragon", "type": "Crew", "mass_kg": 12000}], "flight_number": 299},
        {"name": "Transporter-11", "rocket": "5e9e1502f499c70000000003", "date_utc": "2026-02-01T00:00:00Z", "success": True, "failures": [], "payloads": [{"id": "payload-1", "type": "Various", "mass_kg": 3800}], "flight_number": 298},
        {"name": "Starlink Group 5-12", "rocket": "5e9e1502f499c70000000001", "date_utc": "2025-12-10T00:00:00Z", "success": False, "failures": [{"reason": "engine failure"}], "payloads": [{"id": "starlink-180", "type": "Satellite", "mass_kg": 630}], "flight_number": 297},
        {"name": "Artemis II", "rocket": "5e9e1502f499c70000000004", "date_utc": "2025-09-01T00:00:00Z", "success": True, "failures": [], "payloads": [{"id": "orion", "type": "Crew", "mass_kg": 26000}], "flight_number": 296},
    ]

    packets = []
    start_time = datetime.utcnow()

    for i in range(target_packets):
        launch = random.choice(launches)
        ts = start_time + timedelta(seconds=i * 0.1)
        packets.append(generate_spacex_telemetry(launch, ts))

        if (i + 1) % 500 == 0:
            print(f"  Progress: {i + 1}/{target_packets}")

    return packets


def main():
    print("=== SpaceX Telemetry Ingestion ===")
    print(f"Target: {TARGET_PACKETS} packets")
    print(f"Output: {OUTPUT_FILE}")

    import os
    os.makedirs("data/ingested", exist_ok=True)

    packets = collect_spacex(TARGET_PACKETS)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(packets, f, indent=2)

    print(f"\nIngestion complete: {len(packets)} packets")
    print(f"Saved to {OUTPUT_FILE}")

    by_mission = defaultdict(int)
    for p in packets:
        m = p["data"].get("mission_name", "Unknown")
        by_mission[m] += 1

    print("\nPackets by mission:")
    for mission, count in sorted(by_mission.items(), key=lambda x: -x[1]):
        print(f"  {mission}: {count}")


if __name__ == "__main__":
    main()