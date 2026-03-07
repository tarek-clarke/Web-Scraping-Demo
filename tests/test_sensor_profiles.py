#!/usr/bin/env python3
"""
Tests for Cadillac 2026 Sensor Profiles
==========================================
Validates:
- Sensor definitions against 2026 specifications
- Fault pattern detection and recovery strategies
- Firmware compatibility matrix
- Track-specific operating ranges
- Public API functions
- Integration with SchemaValidator circuit-breaker ranges
"""

import sys
from pathlib import Path

import pytest  # noqa: F401  (needed by pytest discovery)

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sensor_profiles import (  # noqa: E402
    CADILLAC_2026_SENSORS,
    FIRMWARE_COMPAT_MATRIX,
    PIT_WALL_ALERT_THRESHOLDS,
    PIT_WALL_SLO_SECONDS,
    FaultPattern,
    RecoveryStrategy,
    build_schema_validator_ranges,
    get_sensor_profile,
    get_sensors_with_fault,
    get_track_ranges,
    list_safety_critical_sensors,
    resolve_firmware_field,
)
from src.circuit_breaker import SchemaValidator, TelemetryPacket  # noqa: E402


# ===========================================================================
# Sensor Catalogue — Structural Tests
# ===========================================================================


class TestSensorCatalogueCompleteness:
    """Verify the catalogue covers all F1-required sensors."""

    REQUIRED_SENSORS = [
        "speed",
        "rpm",
        "throttle",
        "brake",
        "gear",
        "drs",
        "engine_temp",
        "brake_temp",
        "tyre_pressure",
        "aero_load",
        "g_force_lateral",
        "g_force_longitudinal",
        "g_force_vertical",
        "heart_rate",
        "ecu_canbus",
    ]

    def test_all_required_sensors_present(self):
        for sensor in self.REQUIRED_SENSORS:
            assert sensor in CADILLAC_2026_SENSORS, f"Missing sensor: {sensor}"

    def test_minimum_15_sensors(self):
        assert len(CADILLAC_2026_SENSORS) >= 15

    def test_all_sensors_have_valid_ranges(self):
        for name, profile in CADILLAC_2026_SENSORS.items():
            lo, hi = profile.global_range()
            assert lo < hi, f"{name}: global_lo must be < global_hi"

    def test_all_sensors_have_valid_nominal_ranges(self):
        for name, profile in CADILLAC_2026_SENSORS.items():
            lo, hi = profile.nominal_range()
            assert lo <= hi, f"{name}: nominal_lo must be <= nominal_hi"

    def test_nominal_within_global_range(self):
        for name, profile in CADILLAC_2026_SENSORS.items():
            glo, ghi = profile.global_range()
            nlo, nhi = profile.nominal_range()
            assert nlo >= glo, f"{name}: nominal_lo below global_lo"
            assert nhi <= ghi, f"{name}: nominal_hi above global_hi"

    def test_all_sensors_have_positive_sample_rate(self):
        for name, profile in CADILLAC_2026_SENSORS.items():
            assert profile.sample_rate_hz > 0, f"{name}: sample_rate_hz must be > 0"

    def test_all_sensors_have_display_name(self):
        for name, profile in CADILLAC_2026_SENSORS.items():
            assert profile.display_name, f"{name}: display_name must be non-empty"

    def test_all_sensors_have_unit(self):
        for name, profile in CADILLAC_2026_SENSORS.items():
            assert profile.unit, f"{name}: unit must be non-empty"

    def test_all_sensors_have_known_faults(self):
        for name, profile in CADILLAC_2026_SENSORS.items():
            assert len(profile.known_faults) >= 1, (
                f"{name}: must declare at least one known fault pattern"
            )

    def test_all_sensors_have_recovery_strategy(self):
        for name, profile in CADILLAC_2026_SENSORS.items():
            assert isinstance(profile.recovery_strategy, RecoveryStrategy), (
                f"{name}: recovery_strategy must be a RecoveryStrategy"
            )


# ===========================================================================
# SensorProfile — Behaviour Tests
# ===========================================================================


class TestSensorProfileBehaviour:

    def test_global_range_returns_tuple(self):
        profile = CADILLAC_2026_SENSORS["speed"]
        lo, hi = profile.global_range()
        assert lo == 0.0
        assert hi == 380.0

    def test_nominal_range_returns_tuple(self):
        profile = CADILLAC_2026_SENSORS["speed"]
        lo, hi = profile.nominal_range()
        assert lo == 0.0
        assert hi == 340.0

    def test_get_track_range_known_track(self):
        profile = CADILLAC_2026_SENSORS["speed"]
        tr = profile.get_track_range("monaco")
        assert tr is not None
        assert tr.lo == 0.0
        assert tr.hi == 295.0

    def test_get_track_range_case_insensitive(self):
        profile = CADILLAC_2026_SENSORS["speed"]
        assert profile.get_track_range("Monaco") is not None
        assert profile.get_track_range("MONACO") is not None

    def test_get_track_range_spaces_vs_underscores(self):
        profile = CADILLAC_2026_SENSORS["engine_temp"]
        assert profile.get_track_range("abu dhabi") is not None
        assert profile.get_track_range("abu_dhabi") is not None

    def test_get_track_range_unknown_track_returns_none(self):
        profile = CADILLAC_2026_SENSORS["speed"]
        assert profile.get_track_range("unknown_circuit") is None

    def test_is_healthy_within_global_range(self):
        profile = CADILLAC_2026_SENSORS["speed"]
        assert profile.is_healthy(250.0) is True

    def test_is_healthy_below_global_range(self):
        profile = CADILLAC_2026_SENSORS["tyre_pressure"]
        assert profile.is_healthy(10.0) is False  # below 15.0 psi

    def test_is_healthy_above_global_range(self):
        profile = CADILLAC_2026_SENSORS["speed"]
        assert profile.is_healthy(500.0) is False  # above 380.0 km/h

    def test_is_healthy_uses_track_range_when_provided(self):
        profile = CADILLAC_2026_SENSORS["speed"]
        # Monaco top speed is 295 km/h; 310 km/h is outside track range
        assert profile.is_healthy(310.0, track="monaco") is False
        # but within global range
        assert profile.is_healthy(310.0) is True

    def test_is_healthy_falls_back_to_global_for_unknown_track(self):
        profile = CADILLAC_2026_SENSORS["speed"]
        assert profile.is_healthy(300.0, track="unknown_track") is True


# ===========================================================================
# Safety-Critical Sensors
# ===========================================================================


class TestSafetyCriticalSensors:

    EXPECTED_CRITICAL = {"engine_temp", "tyre_pressure", "brake", "rpm"}

    def test_safety_critical_sensors_are_marked(self):
        critical = set(list_safety_critical_sensors())
        for sensor in self.EXPECTED_CRITICAL:
            assert sensor in critical, f"{sensor} should be safety_critical"

    def test_list_safety_critical_returns_list_of_strings(self):
        result = list_safety_critical_sensors()
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_non_critical_sensor_not_in_list(self):
        critical = list_safety_critical_sensors()
        # throttle is not safety-critical
        assert "throttle" not in critical


# ===========================================================================
# Fault Patterns
# ===========================================================================


class TestFaultPatterns:

    def test_get_sensors_with_bit_flip_fault(self):
        sensors = get_sensors_with_fault(FaultPattern.BIT_FLIP)
        assert "speed" in sensors
        assert "engine_temp" in sensors
        assert "brake_temp" in sensors

    def test_get_sensors_with_schema_drift_fault(self):
        sensors = get_sensors_with_fault(FaultPattern.FIRMWARE_SCHEMA_DRIFT)
        assert "rpm" in sensors
        assert "engine_temp" in sensors

    def test_get_sensors_with_sensor_dropout_fault(self):
        sensors = get_sensors_with_fault(FaultPattern.SENSOR_DROPOUT)
        assert "tyre_pressure" in sensors
        assert "heart_rate" in sensors

    def test_get_sensors_with_fault_returns_list(self):
        result = get_sensors_with_fault(FaultPattern.BIT_FLIP)
        assert isinstance(result, list)

    def test_all_fault_patterns_enumerated(self):
        fault_values = {f.value for f in FaultPattern}
        expected = {
            "bit_flip", "schema_drift", "sensor_dropout",
            "stuck_value", "noise_burst", "can_bus", "clock_skew",
        }
        assert expected.issubset(fault_values)


# ===========================================================================
# Firmware Compatibility Matrix
# ===========================================================================


class TestFirmwareCompatMatrix:

    def test_known_firmware_versions_present(self):
        expected = {"fw_2024_q4", "fw_2025_pre", "fw_2025_r1", "fw_2026_launch"}
        assert expected.issubset(set(FIRMWARE_COMPAT_MATRIX.keys()))

    def test_resolve_firmware_field_known(self):
        canonical = resolve_firmware_field("TwaterOut", "fw_2024_q4")
        assert canonical == "engine_temp"

    def test_resolve_firmware_field_speed_alias(self):
        canonical = resolve_firmware_field("vCar", "fw_2024_q4")
        assert canonical == "speed"

    def test_resolve_firmware_field_unknown_version(self):
        result = resolve_firmware_field("TwaterOut", "fw_9999")
        assert result is None

    def test_resolve_firmware_field_unknown_field(self):
        result = resolve_firmware_field("nonexistent_field", "fw_2024_q4")
        assert result is None

    def test_all_firmware_aliases_resolve_to_known_sensors(self):
        for fw_version, mapping in FIRMWARE_COMPAT_MATRIX.items():
            for field, canonical in mapping.items():
                assert canonical in CADILLAC_2026_SENSORS, (
                    f"{fw_version}: alias '{field}' → '{canonical}' not in catalogue"
                )

    def test_2026_launch_firmware_is_empty(self):
        # Launch firmware uses canonical names; no aliases needed
        assert FIRMWARE_COMPAT_MATRIX["fw_2026_launch"] == {}


# ===========================================================================
# Public API — get_sensor_profile
# ===========================================================================


class TestGetSensorProfile:

    def test_direct_lookup(self):
        profile = get_sensor_profile("engine_temp")
        assert profile is not None
        assert profile.name == "engine_temp"

    def test_case_insensitive_lookup(self):
        assert get_sensor_profile("ENGINE_TEMP") is not None
        assert get_sensor_profile("Engine_Temp") is not None

    def test_alias_lookup_fw_2024(self):
        profile = get_sensor_profile("TwaterOut")
        assert profile is not None
        assert profile.name == "engine_temp"

    def test_alias_lookup_fw_2025(self):
        profile = get_sensor_profile("nMotor")
        assert profile is not None
        assert profile.name == "rpm"

    def test_unknown_sensor_returns_none(self):
        assert get_sensor_profile("completely_unknown_sensor_xyz") is None


# ===========================================================================
# Public API — get_track_ranges
# ===========================================================================


class TestGetTrackRanges:

    def test_known_track_returns_track_specific_range(self):
        lo, hi = get_track_ranges("speed", "monaco")
        assert lo == 0.0
        assert hi == 295.0

    def test_unknown_track_returns_global_range(self):
        lo, hi = get_track_ranges("speed", "unknown_track")
        assert lo == 0.0
        assert hi == 380.0

    def test_unknown_sensor_returns_none(self):
        result = get_track_ranges("nonexistent_sensor", "monaco")
        assert result is None

    def test_all_track_ranges_valid(self):
        for name, profile in CADILLAC_2026_SENSORS.items():
            for tr in profile.track_ranges:
                assert tr.lo < tr.hi, (
                    f"{name} @ {tr.track}: track range lo must be < hi"
                )


# ===========================================================================
# Integration — SchemaValidator compatibility
# ===========================================================================


class TestSchemaValidatorIntegration:
    """
    Verify that sensor profiles integrate correctly with the circuit breaker's
    SchemaValidator when ranges are injected from the 2026 catalogue.
    """

    def test_build_schema_validator_ranges_returns_dict(self):
        ranges = build_schema_validator_ranges()
        assert isinstance(ranges, dict)
        assert len(ranges) >= 15

    def test_all_catalogue_sensors_in_ranges(self):
        ranges = build_schema_validator_ranges()
        for name in CADILLAC_2026_SENSORS:
            assert name in ranges, f"{name} missing from validator ranges"

    def test_schema_validator_accepts_valid_engine_temp(self):
        ranges = build_schema_validator_ranges()
        validator = SchemaValidator(value_ranges=ranges)
        pkt = TelemetryPacket(sensor="engine_temp", value=95.0)
        ok, reason = validator.validate_packet(pkt)
        assert ok is True, f"Expected valid, got: {reason}"

    def test_schema_validator_rejects_bit_flip_engine_temp(self):
        ranges = build_schema_validator_ranges()
        validator = SchemaValidator(value_ranges=ranges)
        pkt = TelemetryPacket(sensor="engine_temp", value=5000.0)
        ok, reason = validator.validate_packet(pkt)
        assert ok is False
        assert "out_of_range" in reason

    def test_schema_validator_accepts_valid_speed(self):
        ranges = build_schema_validator_ranges()
        validator = SchemaValidator(value_ranges=ranges)
        pkt = TelemetryPacket(sensor="speed", value=320.0)
        ok, reason = validator.validate_packet(pkt)
        assert ok is True

    def test_schema_validator_rejects_negative_speed(self):
        ranges = build_schema_validator_ranges()
        validator = SchemaValidator(value_ranges=ranges)
        pkt = TelemetryPacket(sensor="speed", value=-50.0)
        ok, reason = validator.validate_packet(pkt)
        assert ok is False

    def test_schema_validator_accepts_valid_tyre_pressure(self):
        ranges = build_schema_validator_ranges()
        validator = SchemaValidator(value_ranges=ranges)
        pkt = TelemetryPacket(sensor="tyre_pressure", value=23.0)
        ok, reason = validator.validate_packet(pkt)
        assert ok is True

    def test_schema_validator_rejects_low_tyre_pressure(self):
        ranges = build_schema_validator_ranges()
        validator = SchemaValidator(value_ranges=ranges)
        pkt = TelemetryPacket(sensor="tyre_pressure", value=5.0)  # puncture scenario
        ok, reason = validator.validate_packet(pkt)
        assert ok is False


# ===========================================================================
# Pit Wall Integration
# ===========================================================================


class TestPitWallIntegration:

    def test_alert_thresholds_defined_for_key_sensors(self):
        critical_sensors = {"engine_temp", "tyre_pressure", "brake_temp", "rpm"}
        for sensor in critical_sensors:
            assert sensor in PIT_WALL_ALERT_THRESHOLDS, (
                f"Missing pit wall threshold for {sensor}"
            )

    def test_alert_thresholds_have_warning_and_critical(self):
        for sensor, thresholds in PIT_WALL_ALERT_THRESHOLDS.items():
            assert "warning" in thresholds, f"{sensor}: missing 'warning' threshold"
            assert "critical" in thresholds, f"{sensor}: missing 'critical' threshold"

    def test_slo_seconds_defined(self):
        assert "safety_critical_alert" in PIT_WALL_SLO_SECONDS
        assert "non_critical_alert" in PIT_WALL_SLO_SECONDS

    def test_safety_critical_slo_under_1_second(self):
        assert PIT_WALL_SLO_SECONDS["safety_critical_alert"] < 1.0

    def test_engine_temp_warning_below_critical(self):
        thresholds = PIT_WALL_ALERT_THRESHOLDS["engine_temp"]
        assert thresholds["warning"] < thresholds["critical"]

    def test_tyre_pressure_warning_above_critical(self):
        # For tyre pressure: lower = more dangerous (unlike temperature)
        thresholds = PIT_WALL_ALERT_THRESHOLDS["tyre_pressure"]
        assert thresholds["warning"] > thresholds["critical"]
