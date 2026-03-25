#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.

"""
Clinical Vitals Generator
=========================
A multi-modal data generator for the secondary PhD validation domain.
Provides simulated medical telemetry (heart rate, spO2, core temp) for
cross-domain semantic reconciliation testing.
"""

import random
import time
from typing import Dict, List, Iterator

class ClinicalVitalsGenerator:
    def __init__(self, patient_id: str = "P-001"):
        self.patient_id = patient_id
        self.schema = ["heart_rate", "blood_oxygen_pct", "body_temp_c", "blood_pressure_sys", "blood_pressure_dia"]
        
        # Base states
        self.base_hr = 72.0
        self.base_spo2 = 98.0
        self.base_temp = 37.0

    def generate_packet(self) -> Dict:
        """
        Generates a single clinical telemetry packet.
        """
        packet = {
            "patient_id": self.patient_id,
            "timestamp": time.time(),
            "heart_rate": round(self.base_hr + random.uniform(-5, 5), 2),
            "blood_oxygen_pct": round(self.base_spo2 + random.uniform(-1, 0.5), 1),
            "body_temp_c": round(self.base_temp + random.uniform(-0.2, 0.2), 2),
            "blood_pressure_sys": random.randint(110, 130),
            "blood_pressure_dia": random.randint(70, 85),
            "unit": "clinical"
        }
        return packet

    def stream(self, limit: int = 100) -> Iterator[Dict]:
        """
        Infinite stream of clinical telemetry packets.
        """
        for _ in range(limit):
            yield self.generate_packet()
            time.sleep(0.02) # 50Hz

if __name__ == "__main__":
    gen = ClinicalVitalsGenerator()
    print(f"Streaming clinical vitals for {gen.patient_id}...")
    for packet in gen.stream(limit=5):
        print(packet)
