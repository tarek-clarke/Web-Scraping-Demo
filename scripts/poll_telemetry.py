#!/usr/bin/env python3
"""
Conservative Telemetry Poller Daemon
====================================
Polls all 5 API sources (OpenF1, Finnhub, SpaceX, OpenWeather, openFDA) 
conservatively to build a real-world, high-volume telemetry dataset 
without hitting rate limits.

Usage:
    python3 scripts/poll_telemetry.py --duration 3600  # Run for 1 hour
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime

OUTPUT_FILE = "data/ingested/telemetry_latest.json"

# Ingest rate intervals (seconds)
INTERVALS = {
    "openf1": 2.0,      # Free, no key
    "finnhub": 5.0,     # Limit: 60/min (1 per 1.0s)
    "openfda": 5.0,     # Limit: 240/min (1 per 0.25s)
    "spacex": 10.0,     # Free, rare updates
    "openweather": 90.0 # Limit: 1000/day (1 per 86.4s)
}

# API configuration
KEYS = {
    "finnhub": os.environ.get("FINNHUB_API_KEY", ""),
    "openfda": os.environ.get("OPENFDA_API_KEY", ""),
    "openweather": os.environ.get("OPENWEATHER_API_KEY", "")
}

# Keep track of unique packet keys to prevent duplication in file
SEEN_IDS = {
    "openf1": set(),
    "finnhub": set(),
    "openfda": set(),
    "spacex": set(),
    "openweather": set()
}

def load_existing_seen_ids():
    """Scan existing telemetry_latest.json to populate SEEN_IDS."""
    if not os.path.exists(OUTPUT_FILE):
        return
    try:
        with open(OUTPUT_FILE, 'r') as f:
            packets = json.load(f)
        for p in packets:
            src = p.get("source")
            data = p.get("data", {})
            if src == "openf1" and "timestamp" in p:
                SEEN_IDS["openf1"].add(p["timestamp"])
            elif src == "finnhub" and "timestamp" in data:
                SEEN_IDS["finnhub"].add(data["timestamp"])
            elif src == "openfda" and "safetyreportid" in data:
                SEEN_IDS["openfda"].add(data["safetyreportid"])
            elif src == "spacex" and "flight_number" in data:
                SEEN_IDS["spacex"].add(data["flight_number"])
            elif src == "openweather" and "timestamp" in p:
                SEEN_IDS["openweather"].add(p["timestamp"])
        print(f"Pre-loaded seen IDs: openf1={len(SEEN_IDS['openf1'])}, finnhub={len(SEEN_IDS['finnhub'])}, openfda={len(SEEN_IDS['openfda'])}, spacex={len(SEEN_IDS['spacex'])}, openweather={len(SEEN_IDS['openweather'])}")
    except Exception as e:
        print(f"Error loading existing IDs: {e}")

def api_get(url):
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        # Silently log errors to keep screen clean
        return None

def poll_openf1():
    url = "https://api.openf1.org/v1/car_data?session_key=latest&driver_number=1"
    data = api_get(url)
    if data and isinstance(data, list) and len(data) > 0:
        latest = data[-1]
        ts = latest.get("date")
        if ts and ts not in SEEN_IDS["openf1"]:
            SEEN_IDS["openf1"].add(ts)
            return {
                "source": "openf1",
                "timestamp": ts,
                "data": latest
            }
    return None

def poll_finnhub():
    if not KEYS["finnhub"]:
        return None
    url = f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={KEYS['finnhub']}"
    data = api_get(url)
    if data and "t" in data:
        ts = data["t"]
        if ts not in SEEN_IDS["finnhub"]:
            SEEN_IDS["finnhub"].add(ts)
            return {
                "source": "finnhub",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "current_price": data.get("c"),
                    "high": data.get("h"),
                    "low": data.get("l"),
                    "open": data.get("o"),
                    "previous_close": data.get("pc"),
                    "timestamp": ts
                }
            }
    return None

def poll_openfda():
    base_url = "https://api.fda.gov/drug/event.json?limit=1"
    if KEYS["openfda"]:
        base_url += f"&api_key={KEYS['openfda']}"
    # Add a random skip offset to get different records on each call
    import random
    skip = random.randint(0, 10000)
    data = api_get(f"{base_url}&skip={skip}")
    if data and "results" in data:
        event = data["results"][0]
        report_id = event.get("safetyreportid")
        if report_id and report_id not in SEEN_IDS["openfda"]:
            SEEN_IDS["openfda"].add(report_id)
            patient = event.get("patient", {})
            drugs = patient.get("drug", [])
            reactions = patient.get("reaction", [])
            primary_drug = drugs[0].get("medicinalproduct", "unknown") if drugs else "unknown"
            primary_reaction = reactions[0].get("reactionmeddrapt", "unknown") if reactions else "unknown"
            
            return {
                "source": "clinical",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "safetyreportid": report_id,
                    "patient_age": patient.get("patientonsetage", "unknown"),
                    "patient_sex": patient.get("patientsex", "unknown"),
                    "serious_outcome": event.get("serious", "unknown"),
                    "primary_drug": primary_drug,
                    "primary_reaction": primary_reaction,
                    "drug_count": len(drugs),
                    "reaction_count": len(reactions)
                }
            }
    return None

def poll_spacex():
    url = "https://api.spacexdata.com/v4/launches/latest"
    data = api_get(url)
    if data and "flight_number" in data:
        flight = data["flight_number"]
        if flight not in SEEN_IDS["spacex"]:
            SEEN_IDS["spacex"].add(flight)
            return {
                "source": "spacex",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "flight_number": flight,
                    "mission_name": data.get("name"),
                    "launch_date_utc": data.get("date_utc"),
                    "launch_success": data.get("success"),
                    "rocket": data.get("rocket"),
                    "payload_mass_kg": 0  # Simplified for streaming payload
                }
            }
    return None

def poll_openweather():
    if not KEYS["openweather"]:
        # Fallback to keyless forecast if token missing
        url = "https://api.open-meteo.com/v1/forecast?latitude=59.4370&longitude=24.7536&current_weather=true"
        data = api_get(url)
        if data and "current_weather" in data:
            weather = data["current_weather"]
            ts = weather.get("time")
            if ts and ts not in SEEN_IDS["openweather"]:
                SEEN_IDS["openweather"].add(ts)
                return {
                    "source": "openweather",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "temperature_c": weather.get("temperature"),
                        "wind_speed_kmh": weather.get("windspeed"),
                        "weather_code": weather.get("weathercode")
                    }
                }
    else:
        # Standard OpenWeather API if key provided
        url = f"https://api.openweathermap.org/data/2.5/weather?q=Tallinn&appid={KEYS['openweather']}&units=metric"
        data = api_get(url)
        if data and "dt" in data:
            ts = data["dt"]
            if ts not in SEEN_IDS["openweather"]:
                SEEN_IDS["openweather"].add(ts)
                return {
                    "source": "openweather",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "temperature_c": data.get("main", {}).get("temp"),
                        "humidity_percent": data.get("main", {}).get("humidity"),
                        "pressure_hpa": data.get("main", {}).get("pressure")
                    }
                }
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Conservative Telemetry Poller")
    parser.add_argument("--duration", type=int, default=3600, help="Poller run duration in seconds (default: 3600)")
    args = parser.parse_args()

    print("=== Starting Conservative Telemetry Poller ===")
    print(f"Run Duration: {args.duration} seconds")
    print(f"Output File: {OUTPUT_FILE}")
    
    load_existing_seen_ids()
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    start_time = time.time()
    last_polls = {k: 0.0 for k in INTERVALS.keys()}
    new_packets_count = 0

    try:
        while time.time() - start_time < args.duration:
            now = time.time()
            new_packets = []

            # Check and poll each source if its interval has elapsed
            if now - last_polls["openf1"] >= INTERVALS["openf1"]:
                p = poll_openf1()
                if p: new_packets.append(p)
                last_polls["openf1"] = now

            if now - last_polls["finnhub"] >= INTERVALS["finnhub"]:
                p = poll_finnhub()
                if p: new_packets.append(p)
                last_polls["finnhub"] = now

            if now - last_polls["openfda"] >= INTERVALS["openfda"]:
                p = poll_openfda()
                if p: new_packets.append(p)
                last_polls["openfda"] = now

            if now - last_polls["spacex"] >= INTERVALS["spacex"]:
                p = poll_spacex()
                if p: new_packets.append(p)
                last_polls["spacex"] = now

            if now - last_polls["openweather"] >= INTERVALS["openweather"]:
                p = poll_openweather()
                if p: new_packets.append(p)
                last_polls["openweather"] = now

            # If new packets were found, append them to file
            if new_packets:
                existing = []
                if os.path.exists(OUTPUT_FILE):
                    try:
                        with open(OUTPUT_FILE, 'r') as f:
                            existing = json.load(f)
                    except Exception:
                        pass
                
                existing.extend(new_packets)
                with open(OUTPUT_FILE, 'w') as f:
                    json.dump(existing, f, indent=2)
                
                new_packets_count += len(new_packets)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Saved {len(new_packets)} new packet(s). Total new: {new_packets_count}")

            # Sleep briefly to avoid high CPU spin
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nPoller stopped by user.")

    print(f"\nPoller Finished. Added {new_packets_count} new unique packets.")

if __name__ == "__main__":
    main()
