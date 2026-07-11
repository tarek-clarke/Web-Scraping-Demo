#!/usr/bin/env python3
import json
import random
import os
from datetime import datetime

OUTPUT_FILE = "data/ingested/telemetry_latest.json"
PACKETS_PER_API = 2500

def generate_openf1():
    return {
        "source": "openf1",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "driver_number": random.randint(1, 99),
            "position": random.randint(1, 20),
            "lap_time_ms": random.randint(80000, 120000),
            "pit_stop_count": random.randint(0, 3),
            "tire_compound": random.choice(["soft", "medium", "hard"]),
            "speed_kmh": random.randint(250, 320),
            "throttle": random.randint(80, 100),
            "brake": random.randint(0, 100),
            "drs": random.choice([0, 1]),
        }
    }

def generate_finnhub():
    return {
        "source": "finnhub",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "symbol": random.choice(["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]),
            "current_price": round(random.uniform(50, 500), 2),
            "high": round(random.uniform(100, 600), 2),
            "low": round(random.uniform(50, 300), 2),
            "open": round(random.uniform(50, 500), 2),
            "previous_close": round(random.uniform(50, 500), 2),
            "volume": random.randint(1000000, 50000000),
            "timestamp": random.randint(1700000000, 1800000000),
        }
    }

def generate_spacex():
    return {
        "source": "spacex",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "flight_number": random.randint(100, 300),
            "mission_name": random.choice(["Starlink", "Transporter", "CRS", "Demo"]),
            "launch_date_utc": datetime.utcnow().isoformat(),
            "launch_success": random.choice([True, True, True, False]),
            "rocket": random.choice(["Falcon 9", "Falcon Heavy"]),
            "payload_mass_kg": random.randint(1000, 20000),
            "orbit": random.choice(["LEO", "GTO", "ISS", "SSO"]),
            "webcast": random.choice([True, False]),
            "recovery_attempt": random.choice([True, False]),
            "recovery_success": random.choice([True, False]),
        }
    }

def generate_openweather():
    return {
        "source": "openweather",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "temperature_c": round(random.uniform(-10, 40), 1),
            "humidity_percent": random.randint(20, 100),
            "wind_speed_kmh": random.randint(0, 100),
            "wind_direction_deg": random.randint(0, 360),
            "pressure_hpa": random.randint(980, 1050),
            "precipitation_mm": round(random.uniform(0, 50), 1),
            "cloud_cover_percent": random.randint(0, 100),
            "visibility_km": random.randint(1, 50),
            "uv_index": random.randint(0, 11),
            "weather_code": random.randint(0, 99),
        }
    }

# Dynamic import for ClinicalVitalsGenerator
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.generators.clinical_vitals import ClinicalVitalsGenerator

def generate_clinical(gen):
    packet = gen.generate_packet()
    return {
        "source": "clinical",
        "timestamp": packet["timestamp"],
        "data": {k: v for k, v in packet.items() if k not in ["patient_id", "timestamp"]}
    }

def main():
    os.makedirs("data/ingested", exist_ok=True)
    packets = []
    
    clinical_gen = ClinicalVitalsGenerator(drift_probability=0.0) # Generate clean base packets; chaos injector will apply drift during execution

    for _ in range(PACKETS_PER_API):
        packets.append(generate_openf1())
    for _ in range(PACKETS_PER_API):
        packets.append(generate_finnhub())
    for _ in range(PACKETS_PER_API):
        packets.append(generate_spacex())
    for _ in range(PACKETS_PER_API):
        packets.append(generate_openweather())
    for _ in range(PACKETS_PER_API):
        packets.append(generate_clinical(clinical_gen))

    random.shuffle(packets)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(packets, f, indent=2)

    print(f"Generated {len(packets)} packets ({PACKETS_PER_API} per API)")
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()