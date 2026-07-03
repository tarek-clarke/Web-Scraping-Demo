#!/usr/bin/env python3
"""
generate_synthetic_race.py — Simulates a real-time, full-density F1 live telemetry stream.
Generates updates for all 20 drivers at 3.7 Hz (~74 packets/second total)
and writes them to the active target file to stress-test the decoder pipeline.
"""

import os
import sys
import json
import time
import random
from datetime import datetime

# Active F1 Driver Numbers
DRIVERS = [1, 11, 44, 63, 16, 55, 4, 81, 14, 18, 10, 31, 23, 2, 3, 22, 77, 24, 20, 27]

def generate_telemetry_packet(driver: int, session_key: int = 11317) -> dict:
    """Generates a realistic OpenF1 telemetry packet for a driver."""
    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")
    
    # Simulate realistic racing behavior (simple state machine)
    # Gear 1-8, Speed 80-330 km/h, RPM 8000-12000, Throttle 0-100%, Brake 0/100
    gear = random.randint(3, 8)
    speed = int(gear * 40 + random.randint(0, 30))
    rpm = int(speed * 30 + 5000 + random.randint(-500, 500))
    throttle = 100 if random.random() > 0.3 else 0
    brake = 100 if throttle == 0 else 0
    drs = random.choice([0, 8, 10, 12])

    return {
        "source": "openf1",
        "timestamp": now_str + "Z",
        "data": {
            "date": now_str,
            "driver_number": driver,
            "rpm": rpm,
            "speed": speed,
            "gear": gear,
            "throttle": throttle,
            "brake": brake,
            "drs": drs,
            "n_gear": 0,
            "session_key": session_key
        }
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/generate_synthetic_race.py <target_file> [duration_seconds]")
        sys.exit(1)

    target_path = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 300  # Default to 5 minutes

    print(f"[Simulator] Starting synthetic F1 race stream simulation...")
    print(f"[Simulator] Target file: {target_path}")
    print(f"[Simulator] Drivers simulated: {len(DRIVERS)}")
    print(f"[Simulator] Polling rate: 3.7 Hz per driver (~74 packets/sec)")
    print(f"[Simulator] Running for {duration} seconds...")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    # Polling interval per driver tick (3.7 Hz is approx 270ms)
    tick_interval = 1.0 / 3.7
    start_time = time.time()
    packet_count = 0
    tick_count = 0

    try:
        while time.time() - start_time < duration:
            tick_start = time.time()
            
            # Generate a packet for all 20 drivers
            batch = []
            for driver in DRIVERS:
                packet = generate_telemetry_packet(driver)
                batch.append(json.dumps(packet) + "\n")
                packet_count += 1

            # Append batch to target file in a single write operation (high performance)
            with open(target_path, "a") as f:
                f.writelines(batch)

            tick_count += 1
            if tick_count % 15 == 0:
                elapsed = time.time() - start_time
                rate = packet_count / elapsed if elapsed > 0 else 0
                print(f"[Simulator] Streamed {packet_count:,} packets total ({elapsed:.1f}s elapsed, current rate: {rate:.1f} packets/sec)")

            # Sleep to maintain the 3.7 Hz frequency
            elapsed_tick = time.time() - tick_start
            sleep_time = max(0, tick_interval - elapsed_tick)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[Simulator] Streaming interrupted by user.")
    
    total_elapsed = time.time() - start_time
    print(f"[Simulator] Stream completed! Total packets sent: {packet_count:,} in {total_elapsed:.1f} seconds.")

if __name__ == "__main__":
    main()
