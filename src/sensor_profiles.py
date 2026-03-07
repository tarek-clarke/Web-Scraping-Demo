"""
Cadillac 2026 F1 Sensor Profiles
=================================
Comprehensive sensor definitions for the Cadillac Motorsports 2026 F1 season.

Covers:
- All 15+ telemetry sensors with 2026-specific value ranges
- Known fault patterns per sensor (bit-flip, schema drift, dropout)
- Recovery strategies per fault type
- Firmware version compatibility matrix
- Track-specific expected operating ranges (Monaco, Monza, Silverstone, etc.)
- Pit wall integration hooks

Usage::

    from src.sensor_profiles import (
        CADILLAC_2026_SENSORS,
        get_sensor_profile,
        get_track_ranges,
        FIRMWARE_COMPAT_MATRIX,
        FaultPattern,
        RecoveryStrategy,
    )

    profile = get_sensor_profile("engine_temp")
    ranges = get_track_ranges("engine_temp", "monaco")
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class FaultPattern(enum.Enum):
    """Known fault patterns observed on Cadillac F1 hardware."""
    BIT_FLIP = "bit_flip"                    # Single-bit corruption → impossible value
    FIRMWARE_SCHEMA_DRIFT = "schema_drift"   # ECU update renames/reorders fields
    SENSOR_DROPOUT = "sensor_dropout"        # Sensor stops transmitting (None / NaN)
    STUCK_VALUE = "stuck_value"              # Value freezes at last reading
    NOISE_BURST = "noise_burst"              # High-frequency transient noise
    CAN_BUS_CORRUPTION = "can_bus"           # CAN-bus framing errors
    CLOCK_SKEW = "clock_skew"                # Duplicate or out-of-order timestamps


class RecoveryStrategy(enum.Enum):
    """Recovery actions for each fault type."""
    DLQ_REPROCESS = "dlq_reprocess"         # Re-run schema normalisation pass
    BERT_RECONCILE = "bert_reconcile"        # Semantic field mapping via BERT
    INTERPOLATE = "interpolate"              # Kalman / linear interpolation
    USE_LAST_KNOWN = "use_last_known"        # Substitute last valid reading
    DROP_PACKET = "drop_packet"              # Discard; flag lap for manual review
    MANUAL_REVIEW = "manual_review"          # Escalate to telemetry engineer
    CLOCK_RESYNC = "clock_resync"            # Align timestamp to GPS epoch


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TrackRange:
    """Typical operating band for a sensor at a specific circuit."""
    track: str
    lo: float
    hi: float
    notes: str = ""


@dataclass
class SensorProfile:
    """
    Full specification for a single Cadillac 2026 F1 telemetry sensor.

    Parameters
    ----------
    name:
        Canonical sensor key (matches ``SchemaValidator.DEFAULT_RANGES``).
    display_name:
        Human-readable label shown on pit-wall dashboard.
    unit:
        SI or derived unit (e.g. ``"°C"``, ``"km/h"``, ``"%"``).
    global_lo / global_hi:
        Physically plausible bounds used by the circuit breaker.
    nominal_lo / nominal_hi:
        Typical operating range during a green-flag lap (softer alert band).
    sample_rate_hz:
        Transmission frequency from the ECU over CAN-bus.
    known_faults:
        Ordered list of fault patterns seen on this sensor in 2025–26 testing.
    recovery_strategy:
        Primary recovery action if a fault is detected.
    firmware_field_aliases:
        Historic firmware field names that map to this canonical sensor name.
        Used by the BERT reconciler and the DLQ reprocessor.
    safety_critical:
        If True, a ``sensor_dropout`` triggers immediate crew chief alert.
    track_ranges:
        Per-circuit operating bands; used for track-specific SLO checks.
    description:
        One-line description for dashboard tooltips.
    """
    name: str
    display_name: str
    unit: str
    global_lo: float
    global_hi: float
    nominal_lo: float
    nominal_hi: float
    sample_rate_hz: float
    known_faults: List[FaultPattern]
    recovery_strategy: RecoveryStrategy
    firmware_field_aliases: List[str] = field(default_factory=list)
    safety_critical: bool = False
    track_ranges: List[TrackRange] = field(default_factory=list)
    description: str = ""

    # ------------------------------------------------------------------
    def global_range(self) -> Tuple[float, float]:
        """Return ``(global_lo, global_hi)`` — used by SchemaValidator."""
        return (self.global_lo, self.global_hi)

    def nominal_range(self) -> Tuple[float, float]:
        """Return ``(nominal_lo, nominal_hi)`` — used for dashboard alerts."""
        return (self.nominal_lo, self.nominal_hi)

    def get_track_range(self, track: str) -> Optional[TrackRange]:
        """
        Return the track-specific operating band, or None if not defined.

        Matching is case-insensitive and ignores underscores vs. spaces.
        """
        normalised = track.lower().replace(" ", "_")
        for tr in self.track_ranges:
            if tr.track.lower().replace(" ", "_") == normalised:
                return tr
        return None

    def is_healthy(self, value: float, track: Optional[str] = None) -> bool:
        """
        Return True if *value* falls within the relevant operating range.

        Uses the track-specific range when available; falls back to global.
        """
        if track:
            tr = self.get_track_range(track)
            if tr:
                return tr.lo <= value <= tr.hi
        return self.global_lo <= value <= self.global_hi


# ---------------------------------------------------------------------------
# 2026 Cadillac Sensor Catalogue
# ---------------------------------------------------------------------------

CADILLAC_2026_SENSORS: Dict[str, SensorProfile] = {

    # ── Powertrain ──────────────────────────────────────────────────────────

    "speed": SensorProfile(
        name="speed",
        display_name="Car Speed",
        unit="km/h",
        global_lo=0.0,
        global_hi=380.0,
        nominal_lo=0.0,
        nominal_hi=340.0,
        sample_rate_hz=50.0,
        known_faults=[FaultPattern.BIT_FLIP, FaultPattern.STUCK_VALUE],
        recovery_strategy=RecoveryStrategy.USE_LAST_KNOWN,
        firmware_field_aliases=["car_speed", "vCar", "v_car", "speed_kmh"],
        description="Longitudinal car speed from wheel encoders.",
        track_ranges=[
            TrackRange("monaco", 0.0, 295.0, "Low-speed street circuit"),
            TrackRange("monza", 0.0, 370.0, "High-speed power circuit"),
            TrackRange("silverstone", 0.0, 330.0, "Medium-high speed"),
            TrackRange("spa", 0.0, 355.0, "High-speed with Eau Rouge"),
            TrackRange("singapore", 0.0, 310.0, "Street circuit, night race"),
        ],
    ),

    "rpm": SensorProfile(
        name="rpm",
        display_name="Engine RPM",
        unit="RPM",
        global_lo=0.0,
        global_hi=20_000.0,
        nominal_lo=4_000.0,
        nominal_hi=15_500.0,
        sample_rate_hz=100.0,
        known_faults=[
            FaultPattern.BIT_FLIP,
            FaultPattern.FIRMWARE_SCHEMA_DRIFT,
            FaultPattern.SENSOR_DROPOUT,
        ],
        recovery_strategy=RecoveryStrategy.DLQ_REPROCESS,
        firmware_field_aliases=["engineRPM", "engine_rpm", "eng_rpm", "nMotor"],
        safety_critical=True,
        description="Crankshaft rotational speed — primary engine load signal.",
        track_ranges=[
            TrackRange("monaco", 4_000.0, 14_000.0, "Many slow corners"),
            TrackRange("monza", 10_000.0, 15_500.0, "Long full-throttle straights"),
        ],
    ),

    "throttle": SensorProfile(
        name="throttle",
        display_name="Throttle Position",
        unit="%",
        global_lo=0.0,
        global_hi=100.0,
        nominal_lo=0.0,
        nominal_hi=100.0,
        sample_rate_hz=50.0,
        known_faults=[FaultPattern.STUCK_VALUE, FaultPattern.NOISE_BURST],
        recovery_strategy=RecoveryStrategy.USE_LAST_KNOWN,
        firmware_field_aliases=["throttlePos", "tps", "throttle_pct"],
        description="Throttle pedal position as a percentage.",
    ),

    "brake": SensorProfile(
        name="brake",
        display_name="Brake Pressure",
        unit="%",
        global_lo=0.0,
        global_hi=100.0,
        nominal_lo=0.0,
        nominal_hi=100.0,
        sample_rate_hz=50.0,
        known_faults=[FaultPattern.STUCK_VALUE, FaultPattern.SENSOR_DROPOUT],
        recovery_strategy=RecoveryStrategy.USE_LAST_KNOWN,
        firmware_field_aliases=["brakePress", "brake_pct", "brakePressure"],
        safety_critical=True,
        description="Front brake line pressure as a percentage.",
    ),

    "gear": SensorProfile(
        name="gear",
        display_name="Current Gear",
        unit="gear",
        global_lo=0.0,
        global_hi=9.0,
        nominal_lo=1.0,
        nominal_hi=8.0,
        sample_rate_hz=25.0,
        known_faults=[FaultPattern.BIT_FLIP, FaultPattern.CAN_BUS_CORRUPTION],
        recovery_strategy=RecoveryStrategy.USE_LAST_KNOWN,
        firmware_field_aliases=["currentGear", "gearPos", "gear_sel"],
        description="Currently engaged gear (0 = neutral, 9 = reverse in some firmware).",
    ),

    "drs": SensorProfile(
        name="drs",
        display_name="DRS Status",
        unit="state",
        global_lo=0.0,
        global_hi=14.0,
        nominal_lo=0.0,
        nominal_hi=14.0,
        sample_rate_hz=10.0,
        known_faults=[FaultPattern.BIT_FLIP, FaultPattern.FIRMWARE_SCHEMA_DRIFT],
        recovery_strategy=RecoveryStrategy.DLQ_REPROCESS,
        firmware_field_aliases=["drsStatus", "drs_state", "DRS"],
        description="DRS actuator state (FIA encoding: 0=closed, 10=open, 14=fault).",
    ),

    # ── Thermal ─────────────────────────────────────────────────────────────

    "engine_temp": SensorProfile(
        name="engine_temp",
        display_name="Engine Coolant Temp",
        unit="°C",
        global_lo=-40.0,
        global_hi=1000.0,
        nominal_lo=85.0,
        nominal_hi=120.0,
        sample_rate_hz=10.0,
        known_faults=[
            FaultPattern.BIT_FLIP,
            FaultPattern.FIRMWARE_SCHEMA_DRIFT,
            FaultPattern.SENSOR_DROPOUT,
        ],
        recovery_strategy=RecoveryStrategy.DLQ_REPROCESS,
        firmware_field_aliases=[
            "engineTemperature", "coolant_temp", "TwaterOut",
            "eng_temp", "engine_temperature",
        ],
        safety_critical=True,
        description="Engine coolant outlet temperature.",
        track_ranges=[
            TrackRange("bahrain", 85.0, 125.0, "Hot ambient"),
            TrackRange("abu_dhabi", 85.0, 125.0, "Hot ambient"),
            TrackRange("monaco", 85.0, 118.0, "Street circuit, slow laps"),
            TrackRange("monza", 85.0, 115.0, "High speed, good cooling"),
            TrackRange("singapore", 85.0, 122.0, "High humidity, night race"),
        ],
    ),

    "engine_temperature": SensorProfile(
        name="engine_temperature",
        display_name="Engine Temperature (alt.)",
        unit="°C",
        global_lo=-40.0,
        global_hi=1000.0,
        nominal_lo=85.0,
        nominal_hi=120.0,
        sample_rate_hz=10.0,
        known_faults=[FaultPattern.FIRMWARE_SCHEMA_DRIFT],
        recovery_strategy=RecoveryStrategy.BERT_RECONCILE,
        firmware_field_aliases=["engine_temp"],
        description="Alias for engine_temp — present in some ECU firmware revisions.",
    ),

    "brake_temp": SensorProfile(
        name="brake_temp",
        display_name="Brake Disc Temperature",
        unit="°C",
        global_lo=50.0,
        global_hi=1200.0,
        nominal_lo=200.0,
        nominal_hi=900.0,
        sample_rate_hz=20.0,
        known_faults=[
            FaultPattern.BIT_FLIP,
            FaultPattern.SENSOR_DROPOUT,
            FaultPattern.NOISE_BURST,
        ],
        recovery_strategy=RecoveryStrategy.INTERPOLATE,
        firmware_field_aliases=["brakeTemperature", "brake_disc_temp", "TbrakeDisc"],
        description="Carbon-fibre brake disc surface temperature (IR pyrometer).",
        track_ranges=[
            TrackRange("monaco", 200.0, 750.0, "Many braking zones, slow speed"),
            TrackRange("monza", 200.0, 600.0, "Few braking zones"),
            TrackRange("bahrain", 250.0, 900.0, "Hot braking, abrasive tarmac"),
        ],
    ),

    # ── Mechanical ──────────────────────────────────────────────────────────

    "tyre_pressure": SensorProfile(
        name="tyre_pressure",
        display_name="Tyre Pressure",
        unit="psi",
        global_lo=15.0,
        global_hi=35.0,
        nominal_lo=21.0,
        nominal_hi=26.0,
        sample_rate_hz=10.0,
        known_faults=[
            FaultPattern.SENSOR_DROPOUT,
            FaultPattern.STUCK_VALUE,
            FaultPattern.FIRMWARE_SCHEMA_DRIFT,
        ],
        recovery_strategy=RecoveryStrategy.USE_LAST_KNOWN,
        firmware_field_aliases=["tyrePressure", "tyre_psi", "pTyre", "tire_pressure"],
        safety_critical=True,
        description="Front-left tyre pressure (FIA minimum 21 psi in 2026 regs).",
        track_ranges=[
            TrackRange("monaco", 22.0, 26.0, "High lateral load"),
            TrackRange("monza", 21.0, 24.0, "Low downforce setup"),
            TrackRange("silverstone", 21.5, 25.0, "High-speed cornering"),
            TrackRange("bahrain", 22.0, 26.0, "High ambient heat"),
        ],
    ),

    # ── Aerodynamics ────────────────────────────────────────────────────────

    "aero_load": SensorProfile(
        name="aero_load",
        display_name="Aerodynamic Load",
        unit="N",
        global_lo=-500.0,
        global_hi=3_000.0,
        nominal_lo=200.0,
        nominal_hi=2_500.0,
        sample_rate_hz=50.0,
        known_faults=[FaultPattern.BIT_FLIP, FaultPattern.CAN_BUS_CORRUPTION],
        recovery_strategy=RecoveryStrategy.DROP_PACKET,
        firmware_field_aliases=["aeroLoad", "downforce", "F_aero"],
        description="Combined aerodynamic downforce from front and rear wings.",
        track_ranges=[
            TrackRange("monaco", 800.0, 2_500.0, "Maximum downforce setup"),
            TrackRange("monza", 200.0, 1_200.0, "Minimum downforce (low drag)"),
        ],
    ),

    # ── Inertial & Driver ────────────────────────────────────────────────────

    "g_force_lateral": SensorProfile(
        name="g_force_lateral",
        display_name="Lateral G-Force",
        unit="G",
        global_lo=-8.0,
        global_hi=8.0,
        nominal_lo=-6.0,
        nominal_hi=6.0,
        sample_rate_hz=100.0,
        known_faults=[FaultPattern.BIT_FLIP, FaultPattern.NOISE_BURST],
        recovery_strategy=RecoveryStrategy.INTERPOLATE,
        firmware_field_aliases=["gLat", "lateral_g", "g_lat"],
        description="Driver lateral acceleration measured by IMU.",
    ),

    "g_force_longitudinal": SensorProfile(
        name="g_force_longitudinal",
        display_name="Longitudinal G-Force",
        unit="G",
        global_lo=-8.0,
        global_hi=8.0,
        nominal_lo=-6.0,
        nominal_hi=5.0,
        sample_rate_hz=100.0,
        known_faults=[FaultPattern.BIT_FLIP, FaultPattern.NOISE_BURST],
        recovery_strategy=RecoveryStrategy.INTERPOLATE,
        firmware_field_aliases=["gLon", "longitudinal_g", "g_lon"],
        description="Driver longitudinal acceleration (positive = braking).",
    ),

    "g_force_vertical": SensorProfile(
        name="g_force_vertical",
        display_name="Vertical G-Force",
        unit="G",
        global_lo=-5.0,
        global_hi=5.0,
        nominal_lo=-3.0,
        nominal_hi=3.0,
        sample_rate_hz=100.0,
        known_faults=[FaultPattern.BIT_FLIP, FaultPattern.NOISE_BURST],
        recovery_strategy=RecoveryStrategy.INTERPOLATE,
        firmware_field_aliases=["gVert", "vertical_g", "g_vert"],
        description="Vertical acceleration (kerbs, bumps, ride height).",
    ),

    "heart_rate": SensorProfile(
        name="heart_rate",
        display_name="Driver Heart Rate",
        unit="bpm",
        global_lo=30.0,
        global_hi=250.0,
        nominal_lo=60.0,
        nominal_hi=200.0,
        sample_rate_hz=1.0,
        known_faults=[
            FaultPattern.SENSOR_DROPOUT,
            FaultPattern.NOISE_BURST,
            FaultPattern.FIRMWARE_SCHEMA_DRIFT,
        ],
        recovery_strategy=RecoveryStrategy.USE_LAST_KNOWN,
        firmware_field_aliases=["driverHR", "hr_bpm", "heartRate", "HR"],
        description="Driver biometric signal from steering-wheel sensor patch.",
    ),

    # ── Electrical / ECU ─────────────────────────────────────────────────────

    "ecu_canbus": SensorProfile(
        name="ecu_canbus",
        display_name="ECU CAN-Bus Signal",
        unit="raw",
        global_lo=-1_000_000.0,
        global_hi=1_000_000.0,
        nominal_lo=-100_000.0,
        nominal_hi=100_000.0,
        sample_rate_hz=500.0,
        known_faults=[
            FaultPattern.CAN_BUS_CORRUPTION,
            FaultPattern.BIT_FLIP,
            FaultPattern.FIRMWARE_SCHEMA_DRIFT,
            FaultPattern.CLOCK_SKEW,
        ],
        recovery_strategy=RecoveryStrategy.DLQ_REPROCESS,
        firmware_field_aliases=["canBus", "ecu_can", "CANbus_raw"],
        description="Raw ECU CAN-bus byte stream for cross-sensor correlation.",
    ),
}


# ---------------------------------------------------------------------------
# Firmware Compatibility Matrix
# ---------------------------------------------------------------------------
# Maps ECU firmware versions to the sensor field aliases they emit.
# The DLQ reprocessor consults this to normalise schema-drifted packets.

FIRMWARE_COMPAT_MATRIX: Dict[str, Dict[str, str]] = {
    "fw_2024_q4": {
        # firmware key → canonical sensor name
        "TwaterOut":        "engine_temp",
        "TbrakeDisc":       "brake_temp",
        "nMotor":           "rpm",
        "vCar":             "speed",
        "tyrePressure":     "tyre_pressure",
        "aeroLoad":         "aero_load",
        "gLat":             "g_force_lateral",
        "gLon":             "g_force_longitudinal",
        "gVert":            "g_force_vertical",
        "driverHR":         "heart_rate",
        "canBus":           "ecu_canbus",
    },
    "fw_2025_pre": {
        "engine_temperature": "engine_temp",  # field rename in this firmware
        "coolant_temp":       "engine_temp",
        "eng_rpm":            "rpm",
        "car_speed":          "speed",
        "tyre_psi":           "tyre_pressure",
        "downforce":          "aero_load",
        "lateral_g":          "g_force_lateral",
        "longitudinal_g":     "g_force_longitudinal",
        "vertical_g":         "g_force_vertical",
        "hr_bpm":             "heart_rate",
    },
    "fw_2025_r1": {
        # Mid-season ECU update — aliases stabilised toward canonical names
        "engine_temp":     "engine_temp",
        "brake_temp":      "brake_temp",
        "rpm":             "rpm",
        "speed":           "speed",
        "tyre_pressure":   "tyre_pressure",
        "aero_load":       "aero_load",
        "g_force_lateral": "g_force_lateral",
    },
    "fw_2026_launch": {
        # 2026 season launch firmware — all canonical names, no drift expected
    },
}


# ---------------------------------------------------------------------------
# Pit Wall Integration Hooks
# ---------------------------------------------------------------------------

#: Alert severity thresholds used by the pit wall dashboard.
PIT_WALL_ALERT_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "engine_temp": {
        "warning": 115.0,    # °C — engineer notified
        "critical": 125.0,   # °C — crew chief alerted, lap delta suspended
    },
    "tyre_pressure": {
        "warning": 22.5,     # psi (lower bound)
        "critical": 21.0,    # psi — potential delamination risk
    },
    "brake_temp": {
        "warning": 850.0,    # °C
        "critical": 1_000.0,  # °C — immediate slow-down command
    },
    "rpm": {
        "warning": 15_000.0,
        "critical": 15_500.0,  # Engine mapping switches automatically above this
    },
    "heart_rate": {
        "warning": 185.0,    # bpm
        "critical": 210.0,   # bpm — FIA medical delegate notified
    },
}

#: Response time SLOs (seconds) for the pit wall alerting pipeline.
PIT_WALL_SLO_SECONDS: Dict[str, float] = {
    "safety_critical_alert":   0.250,   # < 250 ms end-to-end
    "non_critical_alert":      1.000,   # < 1 s
    "dlq_depth_check":        30.000,   # < 30 s during live running
    "post_race_report":      300.000,   # < 5 min after chequered flag
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_sensor_profile(sensor_name: str) -> Optional[SensorProfile]:
    """
    Return the :class:`SensorProfile` for *sensor_name*, or ``None``.

    The lookup is normalised (case-insensitive, spaces → underscores) and
    also searches firmware alias tables so older field names resolve correctly.

    Examples
    --------
    >>> get_sensor_profile("engine_temp")
    SensorProfile(name='engine_temp', ...)
    >>> get_sensor_profile("TwaterOut")   # fw_2024_q4 alias
    SensorProfile(name='engine_temp', ...)
    """
    key = sensor_name.lower().replace(" ", "_")

    # Direct lookup
    if key in CADILLAC_2026_SENSORS:
        return CADILLAC_2026_SENSORS[key]

    # Alias lookup across all firmware versions
    for fw_map in FIRMWARE_COMPAT_MATRIX.values():
        canonical = fw_map.get(sensor_name) or fw_map.get(key)
        if canonical and canonical in CADILLAC_2026_SENSORS:
            return CADILLAC_2026_SENSORS[canonical]

    return None


def get_track_ranges(sensor_name: str, track: str) -> Optional[Tuple[float, float]]:
    """
    Return ``(lo, hi)`` for *sensor_name* at *track*, or the global range
    if no track-specific entry exists.

    Returns ``None`` if the sensor is not found at all.
    """
    profile = get_sensor_profile(sensor_name)
    if profile is None:
        return None
    tr = profile.get_track_range(track)
    if tr:
        return (tr.lo, tr.hi)
    return profile.global_range()


def build_schema_validator_ranges() -> Dict[str, Tuple[float, float]]:
    """
    Return a ``value_ranges`` dict suitable for passing to
    :class:`src.circuit_breaker.SchemaValidator`.

    This consolidates the 2026 sensor catalogue into the format expected
    by the circuit breaker's range-check logic.
    """
    return {name: profile.global_range() for name, profile in CADILLAC_2026_SENSORS.items()}


def list_safety_critical_sensors() -> List[str]:
    """Return the names of all sensors marked ``safety_critical=True``."""
    return [name for name, p in CADILLAC_2026_SENSORS.items() if p.safety_critical]


def resolve_firmware_field(field_name: str, firmware_version: str) -> Optional[str]:
    """
    Resolve a raw firmware field name to its canonical sensor name for the
    given firmware version.

    Returns ``None`` if the field is not in the compatibility matrix.
    """
    fw_map = FIRMWARE_COMPAT_MATRIX.get(firmware_version, {})
    return fw_map.get(field_name)


def get_sensors_with_fault(fault: FaultPattern) -> List[str]:
    """Return all sensor names that list *fault* as a known fault pattern."""
    return [
        name for name, p in CADILLAC_2026_SENSORS.items()
        if fault in p.known_faults
    ]
