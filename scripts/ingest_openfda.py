#!/usr/bin/env python3
"""
openFDA Drug Events Ingestion Script
====================================
Fetches patient safety reports and adverse drug events from the official openFDA API.
Integrates this as the live healthcare/clinical telemetry source in the Resilient RAP framework.

Usage:
    export OPENFDA_API_KEY="your_api_key_here"  # Optional
    python3 scripts/ingest_openfda.py
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime

OUTPUT_FILE = "data/ingested/telemetry_latest.json"
TARGET_PACKETS = 2500

def fetch_openfda_events(limit=100, skip=0, api_key=None):
    """Fetch drug event records from openFDA REST API."""
    base_url = "https://api.fda.gov/drug/event.json"
    params = {
        "limit": limit,
        "skip": skip
    }
    if api_key:
        params["api_key"] = api_key

    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    print(f"Querying openFDA: {url}")
    
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("results", [])
    except Exception as e:
        print(f"Error querying openFDA API: {e}")
        return []

def format_event_to_packet(event):
    """Format openFDA event JSON into standard Resilient RAP telemetry packet."""
    patient = event.get("patient", {})
    drugs = patient.get("drug", [])
    reactions = patient.get("reaction", [])
    
    # Extract primary drug name if available
    primary_drug = "unknown"
    if drugs and isinstance(drugs, list):
        primary_drug = drugs[0].get("medicinalproduct", "unknown")

    # Extract primary reaction if available
    primary_reaction = "unknown"
    if reactions and isinstance(reactions, list):
        primary_reaction = reactions[0].get("reactionmeddrapt", "unknown")

    # Format timestamp
    recv_date = event.get("receivedate", "")
    try:
        if len(recv_date) == 8: # YYYYMMDD
            dt = datetime.strptime(recv_date, "%Y%m%d")
            timestamp = dt.isoformat()
        else:
            timestamp = datetime.utcnow().isoformat()
    except Exception:
        timestamp = datetime.utcnow().isoformat()

    return {
        "source": "clinical",
        "timestamp": timestamp,
        "data": {
            "safetyreportid": event.get("safetyreportid", "unknown"),
            "patient_age": patient.get("patientonsetage", "unknown"),
            "patient_sex": patient.get("patientsex", "unknown"),
            "serious_outcome": event.get("serious", "unknown"),
            "primary_drug": primary_drug,
            "primary_reaction": primary_reaction,
            "drug_count": len(drugs),
            "reaction_count": len(reactions),
            "company_number": event.get("companynumb", "unknown")
        }
    }

def main():
    print("=== openFDA Telemetry Ingester ===")
    api_key = os.environ.get("OPENFDA_API_KEY")
    if not api_key:
        print("Note: OPENFDA_API_KEY environment variable not set. Running with default rate limits.")
    else:
        print("Using provided openFDA API key.")

    packets = []
    chunk_size = 100
    
    for skip in range(0, TARGET_PACKETS, chunk_size):
        limit = min(chunk_size, TARGET_PACKETS - skip)
        events = fetch_openfda_events(limit=limit, skip=skip, api_key=api_key)
        if not events:
            print("Failed to retrieve events or rate limit reached. Exiting.")
            break
            
        for event in events:
            packets.append(format_event_to_packet(event))
            
        print(f"Progress: {len(packets)}/{TARGET_PACKETS} healthcare packets formatted")

    if not packets:
        print("No packets generated. Telemetry file unchanged.")
        sys.exit(1)

    # Load existing telemetry_latest.json if it exists
    existing_packets = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r') as f:
                existing_packets = json.load(f)
            print(f"Loaded {len(existing_packets)} existing telemetry packets.")
        except Exception as e:
            print(f"Could not load existing telemetry file: {e}")

    # Remove previous clinical packets from array to prevent duplication
    existing_packets = [p for p in existing_packets if p.get("source") != "clinical"]

    # Merge and save
    merged_packets = existing_packets + packets
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(merged_packets, f, indent=2)

    print(f"\nSuccessfully merged and saved {len(merged_packets)} total packets to {OUTPUT_FILE}")
    print(f"Healthcare packets added: {len(packets)}")

if __name__ == "__main__":
    main()
