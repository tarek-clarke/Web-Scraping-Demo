#!/usr/bin/env python3
"""
generate_100k_blast.py — Blasts 100,000 synthetic F1 telemetry packets to a target file.
Used for high-throughput stress testing on LUMI.
"""

import os
import sys
import json
import time
from datetime import datetime

DRIVERS = [1, 11, 44, 63, 16, 55, 4, 81, 14, 18, 10, 31, 23, 2, 3, 22, 77, 24, 20, 27]

def generate_telemetry_packet(driver: int, seq: int) -> dict:
    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")
    return {
        "source": "openf1",
        "timestamp": now_str + "Z",
        "data": {
            "date": now_str,
            "driver_number": driver,
            "rpm": 10000 + (seq % 2000),
            "speed": 150 + (seq % 150),
            "gear": 3 + (seq % 5),
            "throttle": 100 if (seq % 3 != 0) else 0,
            "brake": 0 if (seq % 3 != 0) else 100,
            "drs": 8 if (seq % 10 == 0) else 0,
            "n_gear": 0,
            "session_key": 11317
        }
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/generate_100k_blast.py <target_file>")
        sys.exit(1)

    target_path = sys.argv[1]
    total_packets = 100000
    batch_size = 5000

    print(f"[Blaster] Blasting {total_packets:,} packets to {target_path}...")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    
    # If the file already exists, clear it
    if os.path.exists(target_path):
        os.remove(target_path)
    
    start_time = time.time()
    
    for i in range(0, total_packets, batch_size):
        batch = []
        for j in range(batch_size):
            seq = i + j
            driver = DRIVERS[seq % len(DRIVERS)]
            packet = generate_telemetry_packet(driver, seq)
            batch.append(json.dumps(packet) + "\n")
            
        with open(target_path, "a") as f:
            f.writelines(batch)
            
        elapsed = time.time() - start_time
        print(f"[Blaster] Written {i + batch_size:,} / {total_packets:,} packets ({elapsed:.2f}s elapsed)")
        # Slight pause to let decoder read in chunks if it's running in background
        time.sleep(0.1)

    total_elapsed = time.time() - start_time
    print(f"[Blaster] Complete! Wrote {total_packets:,} packets in {total_elapsed:.2f} seconds.")

if __name__ == "__main__":
    main()
