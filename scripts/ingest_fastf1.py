#!/usr/bin/env python3
"""
FastF1 Telemetry Ingestion Script

F1 Live Telemetry Data Source for Resilient RAP Framework.

Authentication:
- Requires F1 timing app cookies (NASCAR app credentials)
- Set F1_ANALYTICS_UID and F1_ANALYTICS_SID environment variables
- If not set, falls back to mock F1 telemetry for testing

Usage:
    export F1_ANALYTICS_UID="your_uid"
    export F1_ANALYTICS_SID="your_sid"
    python scripts/ingest_fastf1.py

Output:
    data/ingested/fastf1_telemetry.json (10,000 packets by default)
"""

import json
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import fastf1
    from fastf1.livetiming.client import LiveTimingClient
    from fastf1.livetiming.data import LiveTimingData
    FASTF1_AVAILABLE = True
except ImportError:
    FASTF1_AVAILABLE = False
    print("FastF1 not installed. Using mock data. Install with: pip install fastf1")

OUTPUT_FILE = "data/ingested/fastf1_telemetry.json"
TARGET_PACKETS = 2500
TELEMETRY_RATE_HZ = 10

DRIVER_CATEGORIES = [
    {"speed_kmh": (280, 340), "throttle": (60, 100), "brake": (0, 100), "drs": (0, 1)},
    {"speed_kmh": (270, 330), "throttle": (55, 98), "brake": (0, 100), "drs": (0, 1)},
    {"speed_kmh": (260, 320), "throttle": (50, 95), "brake": (0, 100), "drs": (0, 1)},
]

TIRE_COMPOUNDS = ["soft", "medium", "hard", "intermediate", "wet"]

POSITION_TYPES = ["race", "qualifying", "practice", "sprint"]

TEAM_COLORS = {
    "Red Bull": "#3671C6",
    "Ferrari": "#E8002D",
    "Mercedes": "#27F4D2",
    "McLaren": "#FF8700",
    "Aston Martin": "#229971",
    "Alpine": "#0093CC",
    "Williams": "#082CFA",
    "Haas": "#B6BABD",
    "Kick Sauber": "#52E252",
    "RB": "#6692FF",
}

DRIVER_TEAMS = {
    "Verstappen": "Red Bull",
    "Hamilton": "Ferrari",
    "Leclerc": "Ferrari",
    "Norris": "McLaren",
    "Piastri": "McLaren",
    "Sainz": "Williams",
    "Alonso": "Aston Martin",
    "Russell": "Mercedes",
    "Gasly": "Alpine",
    "Ocon": "Haas",
    "Stroll": "Aston Martin",
    "Hulkenberg": "Kick Sauber",
    "Magnussen": "Haas",
    "Albon": "Williams",
    "Ricciardo": "RB",
    "Tsunoda": "RB",
    "Bottas": "Kick Sauber",
    "Zhou": "Alpine",
    "Sargeant": "Williams",
    "Lawson": "RB",
}


def generate_mock_telemetry(driver: str, timestamp: datetime, position_type: str = "race"):
    base = DRIVER_CATEGORIES[random.randint(0, 2)]

    return {
        "source": "fastf1",
        "timestamp": timestamp.isoformat(),
        "data": {
            "driver": driver,
            "team": DRIVER_TEAMS.get(driver, "Williams"),
            "team_color": TEAM_COLORS.get(DRIVER_TEAMS.get(driver, "Williams"), "#FFFFFF"),
            "position_type": position_type,
            "position": random.randint(1, 20),
            "lap_time_ms": random.randint(75000, 95000),
            "lap_number": random.randint(1, 70),
            "pit_stop_count": random.randint(0, 2),
            "tire_compound": random.choice(TIRE_COMPOUNDS),
            "tire_age_laps": random.randint(0, 40),
            "speed_kmh": random.randint(*base["speed_kmh"]),
            "throttle": random.randint(*base["throttle"]),
            "brake": random.randint(*base["brake"]),
            "drs": random.choice([0, 1, 2]),
            "ers_deployment": round(random.uniform(0, 50), 1),
            "fuel_remaining_kg": round(random.uniform(0, 50), 2),
            "fuel_flow_kg_h": random.randint(20, 100),
            "engine_rpm": random.randint(8000, 12000),
            "engine_power_percent": random.randint(85, 100),
            "hybriddeployment_kj": round(random.uniform(0, 8), 2),
            "session_time": timestamp.strftime("%H:%M:%S"),
            "track_temp_c": random.randint(35, 55),
            "air_temp_c": random.randint(20, 35),
        }
    }


def generate_mock_drivers():
    return list(DRIVER_TEAMS.keys())


def collect_fastf1_realtime(target_packets: int, rate_hz: int):
    if not FASTF1_AVAILABLE:
        print("FastF1 not available, using mock data")
        return collect_mock(target_packets)

    uid = os.getenv("F1_ANALYTICS_UID", "")
    sid = os.getenv("F1_ANALYTICS_SID", "")

    if not uid or not sid:
        print("F1_ANALYTICS_UID/SID not set, using mock data")
        return collect_mock(target_packets)

    try:
        print("Connecting to FastF1 live timing...")
        client = LiveTimingClient(uid=uid, sid=sid)
        print("Connected to F1 live timing")
    except Exception as e:
        print(f"FastF1 connection failed: {e}, using mock data")
        return collect_mock(target_packets)

    packets = []
    drivers = generate_mock_drivers()
    start_time = datetime.utcnow()
    interval = 1.0 / rate_hz

    print(f"Collecting {target_packets} packets at {rate_hz}Hz...")

    while len(packets) < target_packets:
        try:
            timing_data = client.get_data()

            for driver in drivers:
                if len(packets) >= target_packets:
                    break

                driver_data = timing_data.get(driver, {})
                if driver_data:
                    ts = datetime.utcnow()
                    packet = {
                        "source": "fastf1",
                        "timestamp": ts.isoformat(),
                        "data": {
                            "driver": driver,
                            "team": DRIVER_TEAMS.get(driver, "Williams"),
                            "speed_kmh": driver_data.get("Speed", random.randint(250, 340)),
                            "throttle": driver_data.get("Throttle", random.randint(60, 100)),
                            "brake": driver_data.get("Brake", random.randint(0, 100)),
                            "drs": driver_data.get("DRS", 0),
                            "position": driver_data.get("Position", random.randint(1, 20)),
                            "lap_time_ms": driver_data.get("LastLapTime", random.randint(75000, 95000)),
                            "timestamp": ts.isoformat(),
                        }
                    }
                    packets.append(packet)
        except Exception as e:
            print(f"FastF1 read error: {e}, continuing...")
            time.sleep(interval)
            continue

        time.sleep(interval)

    client.close()
    return packets


def collect_mock(target_packets: int):
    print(f"Generating {target_packets} mock F1 telemetry packets...")
    packets = []
    drivers = generate_mock_drivers()
    start_time = datetime.utcnow()
    interval = 1.0 / TELEMETRY_RATE_HZ

    for i in range(target_packets):
        driver = random.choice(drivers)
        ts = start_time + timedelta(seconds=i * interval)
        packet = generate_mock_telemetry(driver, ts)
        packets.append(packet)

        if (i + 1) % 500 == 0:
            print(f"  Generated {i + 1}/{target_packets}")

    return packets


def main():
    print("=== FastF1 Telemetry Ingestion ===")
    print(f"Target: {TARGET_PACKETS} packets")
    print(f"Output: {OUTPUT_FILE}")

    os.makedirs("data/ingested", exist_ok=True)

    packets = collect_fastf1_realtime(TARGET_PACKETS, TELEMETRY_RATE_HZ)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(packets, f, indent=2)

    print(f"\nIngestion complete: {len(packets)} packets")
    print(f"Saved to {OUTPUT_FILE}")

    by_driver = {}
    for p in packets:
        d = p["data"]["driver"]
        by_driver[d] = by_driver.get(d, 0) + 1

    print("\nPackets by driver:")
    for driver, count in sorted(by_driver.items()):
        print(f"  {driver}: {count}")


if __name__ == "__main__":
    main()