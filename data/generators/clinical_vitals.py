#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.

"""
Clinical Vitals Generator (Synthea-inspired)
===========================================
Generates synthetic medical telemetry with probabilistic schema drift.
Mimics FHIR Observation patterns for Heart Rate, SpO2, and BP.
"""

import json
import random
import time
from datetime import datetime
from typing import List, Dict

# Canonical Clinical Schema
CLINICAL_SCHEMA = {
    "patient_id": "string",
    "heart_rate": "float",      # bpm
    "spo2": "float",            # percent
    "systolic_bp": "float",     # mmHg
    "diastolic_bp": "float",    # mmHg
    "respiratory_rate": "float" # breaths/min
}

# Drift Variations (Synonyms/Noise)
DRIFT_MAP = {
    "heart_rate": ["hr_bpm", "pulse_rate", "rate_observed", "HR", "heart_rate_vitals"],
    "spo2": ["oxygen_sat", "sp02_percent", "o2_saturation", "SPO2", "sat_vitals"],
    "systolic_bp": ["sys_mmHg", "bp_systolic", "systolic_pressure", "upper_bp"],
    "diastolic_bp": ["dia_mmHg", "bp_diastolic", "diastolic_pressure", "lower_bp"],
    "respiratory_rate": ["resp_rate", "breaths_per_min", "RR", "respiration_observed"]
}

class ClinicalVitalsGenerator:
    def __init__(self, drift_probability: float = 0.3):
        self.drift_prob = drift_probability

    def generate_packet(self, patient_id: str = "PAT-9912") -> Dict:
        """Generate a single packet of noisy clinical telemetry."""
        data = {"patient_id": patient_id, "timestamp": datetime.utcnow().isoformat()}
        
        # Base Vitals
        vitals = {
            "heart_rate": round(random.uniform(60, 100), 1),
            "spo2": round(random.uniform(94, 99), 1),
            "systolic_bp": round(random.uniform(110, 140), 1),
            "diastolic_bp": round(random.uniform(70, 90), 1),
            "respiratory_rate": round(random.uniform(12, 18), 1)
        }

        # Apply Drift
        for field, value in vitals.items():
            if random.random() < self.drift_prob:
                drifted_name = random.choice(DRIFT_MAP[field])
                data[drifted_name] = value
            else:
                data[field] = value
                
        return data

def main():
    gen = ClinicalVitalsGenerator(drift_probability=0.5)
    print("Generating Clinical Telemetry Stream (10 packets)...")
    for _ in range(10):
        packet = gen.generate_packet()
        print(json.dumps(packet, indent=2))
        time.sleep(0.1)

if __name__ == "__main__":
    main()
