#!/usr/bin/env python3
"""
download_race_telemetry.py — Retrospectively downloads all car telemetry data 
from today's race session (session_key 11326) driver-by-driver, merges, 
sorts by timestamp, and saves it.
"""

import os
import sys
import urllib.request
import json

def fetch_url(url):
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None

def main():
    session_key = 11326
    output_path = "data/ingested/telemetry_20260705_140000.json"
    
    print(f"=== Retrospective Race Telemetry Downloader ===")
    print(f"Target Session Key: {session_key}")
    print(f"Output File: {output_path}\n")

    # 1. Fetch active drivers for this session
    drivers_url = f"https://api.openf1.org/v1/drivers?session_key={session_key}"
    print(f"Fetching drivers list from {drivers_url}...")
    drivers_data = fetch_url(drivers_url)
    
    if not drivers_data:
        print("ERROR: Could not fetch active drivers.")
        sys.exit(1)

    driver_numbers = [driver["driver_number"] for driver in drivers_data]
    print(f"Detected {len(driver_numbers)} active drivers: {driver_numbers}\n")

    all_packets = []

    # 2. Fetch telemetry driver-by-driver
    for driver in driver_numbers:
        telemetry_url = f"https://api.openf1.org/v1/car_data?session_key={session_key}&driver_number={driver}"
        print(f"Downloading telemetry for Driver {driver:2d}...", end="", flush=True)
        data = fetch_url(telemetry_url)
        if data:
            print(f" Done ({len(data):,} packets)")
            for item in data:
                # Format to match Go Ingestor output packet shape
                all_packets.append({
                    "source": "openf1",
                    "timestamp": item.get("date"),
                    "data": item
                })
        else:
            print(" Failed")

    print(f"\nTotal packets downloaded: {len(all_packets):,}")

    # 3. Sort packets by timestamp to represent true live stream ordering
    print("Sorting packets chronologically...")
    all_packets.sort(key=lambda x: x["timestamp"] or "")

    # 4. Save to JSON Lines format
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"Writing to {output_path}...")
    with open(output_path, "w") as f:
        for packet in all_packets:
            f.write(json.dumps(packet) + "\n")

    print("\n=== Download Complete! ===")
    print(f"Telemetry saved successfully to: {output_path}")

if __name__ == "__main__":
    main()
