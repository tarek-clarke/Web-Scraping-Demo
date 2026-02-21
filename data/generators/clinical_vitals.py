#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
Clinical Vitals Generator.

Generates synthetic ICU telemetry records with vendor-specific schema variants
to simulate schema drift across hospital device manufacturers (GE, Philips, Draeger).

Research justification: multi-vendor schema variance is the primary source of
schema drift in clinical data pipelines, making this a canonical test domain.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Iterator, List
import random


class VendorStyle(str, Enum):
    """Supported ICU device vendor naming conventions."""
    GE = "GE"
    PHILIPS = "Philips"
    DRAEGER = "Draeger"
    STANDARD = "Standard"


# Gold-standard schema field names
STANDARD_SCHEMA: List[str] = [
    "Heart Rate (bpm)",
    "SpO2 (%)",
    "Systolic BP (mmHg)",
    "Diastolic BP (mmHg)",
    "Resp Rate (/min)",
    "Temp (C)",
    "EtCO2 (mmHg)",
]

# Per-vendor messy field name mappings  (standard -> vendor-specific)
VENDOR_SCHEMAS: Dict[str, Dict[str, str]] = {
    VendorStyle.GE: {
        "Heart Rate (bpm)":     "GE_Monitor_v2_HR",
        "SpO2 (%)":             "GE_Monitor_v2_O2",
        "Systolic BP (mmHg)":   "GE_Monitor_v2_SYS",
        "Diastolic BP (mmHg)":  "GE_Monitor_v2_DIA",
        "Resp Rate (/min)":     "GE_Monitor_v2_RR",
        "Temp (C)":             "GE_Temp_Probe",
        "EtCO2 (mmHg)":         "GE_CapnoStat_CO2",
    },
    VendorStyle.PHILIPS: {
        "Heart Rate (bpm)":     "Philips_MX800_HR",
        "SpO2 (%)":             "Philips_MX800_SpO2",
        "Systolic BP (mmHg)":   "Philips_MX800_NBP_SYS",
        "Diastolic BP (mmHg)":  "Philips_MX800_NBP_DIA",
        "Resp Rate (/min)":     "Philips_MX800_RespRate",
        "Temp (C)":             "Philips_MX800_Temp",
        "EtCO2 (mmHg)":         "Philips_MX800_EtCO2",
    },
    VendorStyle.DRAEGER: {
        "Heart Rate (bpm)":     "Drg_Infinity_HR_bpm",
        "SpO2 (%)":             "Drg_Infinity_SpO2_pct",
        "Systolic BP (mmHg)":   "Drg_Infinity_SYS_mmHg",
        "Diastolic BP (mmHg)":  "Drg_Infinity_DIA_mmHg",
        "Resp Rate (/min)":     "Drg_Infinity_RR_brpm",
        "Temp (C)":             "Drg_Infinity_Temp_C",
        "EtCO2 (mmHg)":         "Drg_Infinity_EtCO2",
    },
    VendorStyle.STANDARD: {field: field for field in STANDARD_SCHEMA},
}

# Realistic physiological ranges (min, max)
FIELD_RANGES: Dict[str, tuple] = {
    "Heart Rate (bpm)":    (45, 160),
    "SpO2 (%)":            (85, 100),
    "Systolic BP (mmHg)":  (80, 190),
    "Diastolic BP (mmHg)": (50, 120),
    "Resp Rate (/min)":    (8, 35),
    "Temp (C)":            (35.5, 40.5),
    "EtCO2 (mmHg)":        (20, 55),
}


class ClinicalVitalsGenerator:
    """
    Generates synthetic ICU vital-sign records with vendor-specific field names.

    Supports deterministic seeding for reproducible test data.
    """

    def __init__(self, seed: int = None):
        self._rng = random.Random(seed)

    def get_standard_schema(self) -> List[str]:
        """Return the gold-standard field name list."""
        return list(STANDARD_SCHEMA)

    def get_vendor_schemas(self) -> Dict[str, Dict[str, str]]:
        """Return all vendor field-name mappings keyed by VendorStyle."""
        return {str(k): dict(v) for k, v in VENDOR_SCHEMAS.items()}

    def _sample_value(self, standard_field: str) -> float:
        lo, hi = FIELD_RANGES[standard_field]
        return round(self._rng.uniform(lo, hi), 2)

    def generate_record(self, vendor: VendorStyle = VendorStyle.STANDARD) -> Dict[str, float]:
        """
        Generate one synthetic vitals record using vendor-specific field names.

        Args:
            vendor: Which vendor's naming convention to use.

        Returns:
            dict mapping vendor field names to sampled physiological values.
        """
        mapping = VENDOR_SCHEMAS.get(vendor, VENDOR_SCHEMAS[VendorStyle.STANDARD])
        return {vendor_field: self._sample_value(std_field)
                for std_field, vendor_field in mapping.items()}

    def stream_vitals(
        self,
        num_records: int = 100,
        vendor: VendorStyle = None,
    ) -> Iterator[Dict[str, float]]:
        """
        Yield a stream of synthetic vitals records.

        Args:
            num_records: Number of records to emit.
            vendor: If None, rotates randomly through all vendors to simulate
                    multi-vendor schema drift.

        Yields:
            dict of field_name -> value for each record.
        """
        vendors = list(VENDOR_SCHEMAS.keys())
        for _ in range(num_records):
            v = vendor if vendor is not None else self._rng.choice(vendors)
            yield self.generate_record(vendor=v)
