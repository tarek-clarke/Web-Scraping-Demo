#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
Clinical ICU Stream Generator.

Research justification: simulate domain generalization by emitting ICU telemetry
with hospital-specific schema drift variants.
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Optional
import json
import numpy as np


BASE_FIELDS = ["O2_Sat", "BPM_Radial", "NIBP_Sys", "Vent_Mode"]

HOSPITAL_VARIANTS = {
    "GE": {
        "O2_Sat": "GE_Monitor_v2_O2",
        "BPM_Radial": "GE_Monitor_v2_HR",
        "NIBP_Sys": "GE_Monitor_v2_SYS",
        "Vent_Mode": "GE_Vent_Mode",
    },
    "Philips": {
        "O2_Sat": "Philips_MX800_SpO2",
        "BPM_Radial": "Philips_MX800_HR",
        "NIBP_Sys": "Philips_MX800_SYS",
        "Vent_Mode": "Philips_Vent_Mode",
    },
}


def _random_vitals(rng: np.random.Generator) -> Dict[str, float]:
    return {
        "O2_Sat": float(rng.normal(97.0, 1.5)),
        "BPM_Radial": float(rng.normal(78.0, 8.0)),
        "NIBP_Sys": float(rng.normal(120.0, 12.0)),
        "Vent_Mode": float(rng.integers(1, 5)),
    }


def inject_hospital_drift(packet: Dict[str, float], vendor: str) -> Dict[str, float]:
    """
    Inject hospital-specific schema drift into an ICU packet.
    """
    mapping = HOSPITAL_VARIANTS.get(vendor)
    if not mapping:
        return packet
    return {mapping.get(k, k): v for k, v in packet.items()}


def generate_clinical_stream(
    batch_size: int = 50,
    vendor: str = "GE",
    rng_seed: Optional[int] = None,
) -> Iterator[str]:
    """
    Yield JSON strings representing ICU telemetry packets.
    """
    rng = np.random.default_rng(rng_seed)
    for _ in range(batch_size):
        packet = _random_vitals(rng)
        drifted = inject_hospital_drift(packet, vendor)
        yield json.dumps(drifted)
