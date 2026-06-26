#!/usr/bin/env python3
"""
live_gpu_decoder.py — Real-time GPU-accelerated schema reconciliation
on live OpenF1 telemetry data.

Watches the telemetry_latest.json file as the Go ingestor writes to it,
processes new packets through chaos injection and reconciliation, and
outputs results to data/reports/live_f1/.

Usage:
    python3 live_gpu_decoder.py [--chaos-rate 0.10] [--reconciler bert] [--poll-interval 5]
"""

import argparse
import copy
import csv
import json
import os
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.hardware.detector import HardwareDetector
from src.hardware.vram_prober import VRAMProber
from src.reconciliation.engine import ReconciliationEngine
from src.chaos.json_chaos import JSONChaos
from src.chaos.schema_chaos import SchemaChaos


OUTPUT_DIR = "data/reports/live_f1"
TELEMETRY_FILE = "data/ingested/telemetry_latest.json"


def setup_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return timestamp


def detect_session():
    """Auto-detect the current live F1 session from the OpenF1 API."""
    session_info = {
        "session_name": "Unknown",
        "session_type": "Unknown",
        "country_name": "Unknown",
        "circuit_short_name": "Unknown",
        "session_key": "unknown",
        "year": datetime.utcnow().year,
    }

    try:
        email = os.getenv("OPENF1_EMAIL", "")
        password = os.getenv("OPENF1_PASSWORD", "")
        headers = {}

        if email and password:
            token_resp = requests.post(
                "https://api.openf1.org/token",
                data={"username": email, "password": password},
                timeout=10,
            )
            if token_resp.status_code == 200:
                token = token_resp.json().get("access_token", "")
                if token:
                    headers["Authorization"] = f"Bearer {token}"

        resp = requests.get(
            "https://api.openf1.org/v1/sessions?session_key=latest",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                s = data[0]
            elif isinstance(data, dict):
                s = data
            else:
                return session_info

            session_info["session_name"] = s.get("session_name", "Unknown")
            session_info["session_type"] = s.get("session_type", "Unknown")
            session_info["country_name"] = s.get("country_name", "Unknown")
            session_info["circuit_short_name"] = s.get("circuit_short_name", "Unknown")
            session_info["session_key"] = s.get("session_key", "unknown")
            session_info["year"] = s.get("year", datetime.utcnow().year)
    except Exception as e:
        print(f"[Session] Could not auto-detect session: {e}")

    return session_info


def detect_hardware():
    detector = HardwareDetector()
    hardware = detector.detect()
    prober = VRAMProber(hardware["type"])
    vram_info = prober.probe()

    print("=== Live F1 GPU Decoder ===")
    print(f"GPU Model: {hardware['model']}")
    print(f"Hardware Type: {hardware['type']}")
    print(f"Device: {'cuda' if hardware['type'] in ['cuda', 'rocm'] else 'cpu'}")
    print(f"Total VRAM: {hardware['vram_gb']} GB")
    print(f"Free VRAM: {vram_info['free_gb']:.2f} GB")
    print()

    return hardware, vram_info


def load_packets(filepath, max_backlog=5000):
    """Load packets from the telemetry JSON file. If backlog exceeds max_backlog, return only the last max_backlog packets."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            if len(data) > max_backlog:
                return data[-max_backlog:]
            return data
        return []
    except (json.JSONDecodeError, IOError):
        return []


def inject_chaos(packet, chaos_method, chaos_rate, json_chaos, schema_chaos, rng_seed):
    """Inject chaos into a single packet and return (original, drifted, sub_type)."""
    import random
    random.seed(rng_seed)

    if random.random() > chaos_rate:
        return None  # No drift for this packet

    original = copy.deepcopy(packet)
    drifted = copy.deepcopy(packet)
    data = drifted.get("data", {})

    if chaos_method == "json_manip":
        sub_type, modified = json_chaos.inject_with_subtype(data)
    elif chaos_method == "schema_alter":
        sub_type, modified = schema_chaos.alter_with_subtype(data)
    else:
        sub_type, modified = json_chaos.inject_with_subtype(data)

    drifted["data"] = modified
    return original, drifted, sub_type


def main():
    parser = argparse.ArgumentParser(description="Live F1 GPU Decoder")
    parser.add_argument("--chaos-rate", type=float, default=0.10,
                        help="Chaos injection rate 0-1 (default: 0.10)")
    parser.add_argument("--reconciler", type=str, default="bert",
                        choices=["levenshtein", "regex", "bert"],
                        help="Reconciler to use (default: bert)")
    parser.add_argument("--chaos-method", type=str, default="json_manip",
                        choices=["json_manip", "schema_alter"],
                        help="Chaos injection method (default: json_manip)")
    parser.add_argument("--poll-interval", type=float, default=5.0,
                        help="Seconds between file polls (default: 5)")
    parser.add_argument("--batch-size", type=int, default=16,
                        help="Batch size for reconciliation (default: 16)")
    args = parser.parse_args()

    hardware, vram_info = detect_hardware()
    hw_type = hardware["type"]
    timestamp = setup_output_dir()

    # Auto-detect live session
    print("[Init] Detecting live F1 session...")
    session_info = detect_session()
    session_label = f"{session_info['country_name']} — {session_info['session_name']}"
    print(f"[Session] {session_label}")
    print(f"[Session] Circuit: {session_info['circuit_short_name']}")
    print(f"[Session] Key: {session_info['session_key']}")
    print()

    # Initialize reconciliation engine
    print(f"[Init] Loading {args.reconciler} reconciler on {hw_type}...")
    engine = ReconciliationEngine(hw_type, args.batch_size)
    print(f"[Init] Reconciler ready.")
    print(f"[Init] Chaos method: {args.chaos_method} @ {args.chaos_rate:.0%} rate")
    print(f"[Init] Polling {TELEMETRY_FILE} every {args.poll_interval}s")
    print(f"[Init] Results → {OUTPUT_DIR}/")
    print()

    json_chaos = JSONChaos()
    schema_chaos = SchemaChaos()

    # CSV output for live results
    csv_path = f"{OUTPUT_DIR}/live_results_{timestamp}.csv"
    csv_fields = [
        "timestamp", "packet_idx", "source", "driver_number",
        "chaos_method", "chaos_sub_type", "reconciler",
        "accuracy", "latency_ms", "mapped_fields", "unmapped_fields"
    ]
    csvfile = open(csv_path, "w", newline="")
    writer = csv.DictWriter(csvfile, fieldnames=csv_fields)
    writer.writeheader()

    # Summary stats
    stats = {
        "total_processed": 0,
        "total_drifted": 0,
        "total_reconciled": 0,
        "accuracy_sum": 0.0,
        "latency_sum": 0.0,
    }

    total_packets_seen = 0

    print("=" * 70)
    print(f"  LIVE F1 TELEMETRY DECODER — {session_label}")
    print("=" * 70)

    try:
        while True:
            # We fetch up to 100,000 packets to verify we don't drop updates, but keep memory sane.
            packets = load_packets(TELEMETRY_FILE, max_backlog=100000)
            
            # If we've seen fewer packets than what is loaded, it means we have new packets.
            # When we first start, we only process the latest packets to skip the massive backlog.
            if total_packets_seen == 0:
                total_packets_seen = len(packets)
                # Skip historical backlog to catch up to live edge
                print(f"[Init] Skipping historical backlog of {total_packets_seen:,} packets to keep it truly live.")
                time.sleep(args.poll_interval)
                continue

            new_count = len(packets) - (total_packets_seen if len(packets) >= total_packets_seen else 0)
            
            if new_count <= 0:
                time.sleep(args.poll_interval)
                continue

            batch_start = time.perf_counter()
            drifted_count = 0
            reconciled_count = 0

            # The new packets are the last new_count elements in the array
            new_packets = packets[-new_count:] if new_count < len(packets) else packets

            for idx, packet in enumerate(new_packets):
                i = len(packets) - new_count + idx
                stats["total_processed"] += 1

                result = inject_chaos(
                    packet, args.chaos_method, args.chaos_rate,
                    json_chaos, schema_chaos, rng_seed=i
                )

                if result is None:
                    continue  # No drift, skip

                original, drifted, sub_type = result
                drifted_count += 1
                stats["total_drifted"] += 1

                # Reconcile
                rec_start = time.perf_counter()
                rec_result = engine.reconcile(original, drifted, args.reconciler)
                rec_latency = (time.perf_counter() - rec_start) * 1000

                reconciled_count += 1
                stats["total_reconciled"] += 1
                stats["accuracy_sum"] += rec_result["accuracy"]
                stats["latency_sum"] += rec_latency

                driver_num = packet.get("data", {}).get("driver_number", "?")

                # Write to CSV
                writer.writerow({
                    "timestamp": datetime.utcnow().isoformat(),
                    "packet_idx": i,
                    "source": packet.get("source", "openf1"),
                    "driver_number": driver_num,
                    "chaos_method": args.chaos_method,
                    "chaos_sub_type": sub_type,
                    "reconciler": args.reconciler,
                    "accuracy": round(rec_result["accuracy"], 4),
                    "latency_ms": round(rec_latency, 3),
                    "mapped_fields": rec_result["mapped_fields"],
                    "unmapped_fields": rec_result["unmapped_fields"],
                })
                csvfile.flush()

            batch_elapsed = (time.perf_counter() - batch_start) * 1000
            total_packets_seen = len(packets)

            # Print batch summary
            avg_acc = (stats["accuracy_sum"] / stats["total_reconciled"] * 100) if stats["total_reconciled"] > 0 else 0
            avg_lat = (stats["latency_sum"] / stats["total_reconciled"]) if stats["total_reconciled"] > 0 else 0

            print(
                f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
                f"Processed {new_count:,} new packets | "
                f"Drifted: {drifted_count:,} | "
                f"Reconciled: {reconciled_count:,} | "
                f"Batch: {batch_elapsed:.0f}ms | "
                f"Avg Acc: {avg_acc:.1f}% | "
                f"Avg Lat: {avg_lat:.2f}ms | "
                f"Total: {stats['total_processed']:,}"
            )

            time.sleep(args.poll_interval)

    except KeyboardInterrupt:
        print("\n" + "=" * 70)
        print("  LIVE SESSION ENDED — Writing summary...")
        print("=" * 70)

    csvfile.close()

    # Write summary manifest
    manifest = {
        "run_id": timestamp,
        "session": session_label,
        "session_name": session_info["session_name"],
        "session_type": session_info["session_type"],
        "country": session_info["country_name"],
        "circuit": session_info["circuit_short_name"],
        "session_key": session_info["session_key"],
        "year": session_info["year"],
        "hardware_model": hardware.get("model", "unknown"),
        "hardware_type": hw_type,
        "reconciler": args.reconciler,
        "chaos_method": args.chaos_method,
        "chaos_rate": args.chaos_rate,
        "total_packets_processed": stats["total_processed"],
        "total_drifted": stats["total_drifted"],
        "total_reconciled": stats["total_reconciled"],
        "avg_accuracy": round(stats["accuracy_sum"] / max(stats["total_reconciled"], 1), 4),
        "avg_latency_ms": round(stats["latency_sum"] / max(stats["total_reconciled"], 1), 3),
    }

    manifest_path = f"{OUTPUT_DIR}/manifest_{timestamp}.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n  Results saved to: {csv_path}")
    print(f"  Manifest saved to: {manifest_path}")
    print(f"\n  Total Packets: {stats['total_processed']:,}")
    print(f"  Total Drifted: {stats['total_drifted']:,}")
    print(f"  Total Reconciled: {stats['total_reconciled']:,}")
    if stats["total_reconciled"] > 0:
        print(f"  Avg Accuracy: {stats['accuracy_sum'] / stats['total_reconciled'] * 100:.2f}%")
        print(f"  Avg Latency: {stats['latency_sum'] / stats['total_reconciled']:.3f}ms")
    print()


if __name__ == "__main__":
    main()
