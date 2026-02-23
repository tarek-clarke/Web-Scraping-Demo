#!/usr/bin/env python3
"""
Tests for Cadillac F1 Production Modules
==========================================
Validates: Circuit-Breaker, Edge Buffer, Geo-Fence, and Health Monitor.
"""

import os
import sys
import json
import time
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.circuit_breaker import (
    TelemetryCircuitBreaker,
    TelemetryPacket,
    SchemaValidator,
    DeadLetterQueue,
    CircuitState,
    DLQRecord,
)
from src.local_persistence import (
    TracksideEdgeBuffer,
    BufferedPacket,
    SyncStatus,
)
from src.geo_fence import (
    GeoFence,
    Jurisdiction,
    CIRCUIT_JURISDICTION,
)


# ===================================================================
# Circuit Breaker Tests
# ===================================================================
class TestSchemaValidator:
    def test_valid_speed_packet(self):
        v = SchemaValidator()
        pkt = TelemetryPacket(sensor="speed", value=320.0)
        ok, reason = v.validate_packet(pkt)
        assert ok is True
        assert reason == "OK"

    def test_null_value_rejected(self):
        v = SchemaValidator()
        pkt = TelemetryPacket(sensor="rpm", value=None)
        ok, reason = v.validate_packet(pkt)
        assert ok is False
        assert "null_value" in reason

    def test_string_in_numeric_rejected(self):
        v = SchemaValidator()
        pkt = TelemetryPacket(sensor="throttle", value="OVERHEAT")
        ok, reason = v.validate_packet(pkt)
        assert ok is False
        assert "string_in_numeric" in reason

    def test_out_of_range_rejected(self):
        v = SchemaValidator()
        pkt = TelemetryPacket(sensor="engine_temp", value=5000.0)
        ok, reason = v.validate_packet(pkt)
        assert ok is False
        assert "out_of_range" in reason

    def test_negative_range_rejected(self):
        v = SchemaValidator()
        pkt = TelemetryPacket(sensor="speed", value=-100.0)
        ok, reason = v.validate_packet(pkt)
        assert ok is False
        assert "out_of_range" in reason

    def test_unknown_sensor_passes(self):
        v = SchemaValidator()
        pkt = TelemetryPacket(sensor="custom_sensor_xyz", value=42.0)
        ok, reason = v.validate_packet(pkt)
        assert ok is True


class TestDeadLetterQueue:
    def test_enqueue_and_depth(self, tmp_path):
        dlq = DeadLetterQueue(db_path=str(tmp_path / "test_dlq.sqlite"))
        assert dlq.depth() == 0

        pkt = TelemetryPacket(sensor="speed", value=None)
        record = DLQRecord(packet=pkt, reason="null_value", circuit_state="CLOSED")
        dlq.enqueue(record)
        assert dlq.depth() == 1
        dlq.close()

    def test_recent_returns_records(self, tmp_path):
        dlq = DeadLetterQueue(db_path=str(tmp_path / "test_dlq.sqlite"))
        for i in range(5):
            pkt = TelemetryPacket(sensor=f"sensor_{i}", value=None)
            record = DLQRecord(packet=pkt, reason="test", circuit_state="OPEN")
            dlq.enqueue(record)
        recent = dlq.recent(limit=3)
        assert len(recent) == 3
        dlq.close()

    def test_mark_reprocessed(self, tmp_path):
        dlq = DeadLetterQueue(db_path=str(tmp_path / "test_dlq.sqlite"))
        pkt = TelemetryPacket(packet_id="pkt_001", sensor="rpm", value=None)
        record = DLQRecord(packet=pkt, reason="test", circuit_state="CLOSED")
        dlq.enqueue(record)
        assert dlq.depth() == 1
        dlq.mark_reprocessed("pkt_001")
        assert dlq.depth() == 0
        dlq.close()


class TestCircuitBreaker:
    def test_closed_accepts_valid_packets(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=3, dlq_path=str(tmp_path / "dlq.sqlite")
        )
        pkt = TelemetryPacket(sensor="speed", value=300.0)
        accepted, reason = cb.process(pkt)
        assert accepted is True
        assert reason == "OK"
        assert cb.state == CircuitState.CLOSED
        cb.dlq.close()

    def test_trips_to_open_after_threshold(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=3, dlq_path=str(tmp_path / "dlq.sqlite")
        )
        for _ in range(3):
            pkt = TelemetryPacket(sensor="speed", value=None)
            cb.process(pkt)
        assert cb.state == CircuitState.OPEN
        cb.dlq.close()

    def test_open_rejects_all_packets(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=2, recovery_timeout=100,
            dlq_path=str(tmp_path / "dlq.sqlite"),
        )
        # Trip the breaker
        for _ in range(2):
            cb.process(TelemetryPacket(sensor="speed", value=None))
        assert cb.state == CircuitState.OPEN

        # Valid packet should still be rejected
        accepted, reason = cb.process(TelemetryPacket(sensor="speed", value=200.0))
        assert accepted is False
        assert reason == "circuit_open"
        cb.dlq.close()

    def test_half_open_recovery(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_max_calls=2,
            dlq_path=str(tmp_path / "dlq.sqlite"),
        )
        # Trip the breaker
        for _ in range(2):
            cb.process(TelemetryPacket(sensor="speed", value=None))
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Should transition to HALF_OPEN and accept valid packets
        accepted, _ = cb.process(TelemetryPacket(sensor="speed", value=200.0))
        assert accepted is True
        accepted, _ = cb.process(TelemetryPacket(sensor="speed", value=210.0))
        assert accepted is True

        # After enough successes, should be CLOSED
        assert cb.state == CircuitState.CLOSED
        cb.dlq.close()

    def test_process_batch(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=10, dlq_path=str(tmp_path / "dlq.sqlite")
        )
        packets = [
            TelemetryPacket(sensor="speed", value=300.0),
            TelemetryPacket(sensor="speed", value=None),
            TelemetryPacket(sensor="speed", value=310.0),
        ]
        result = cb.process_batch(packets)
        assert result["accepted"] == 2
        assert result["rejected"] == 1
        cb.dlq.close()

    def test_reset(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=2, dlq_path=str(tmp_path / "dlq.sqlite")
        )
        for _ in range(2):
            cb.process(TelemetryPacket(sensor="speed", value=None))
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        cb.dlq.close()

    def test_metrics(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=5, dlq_path=str(tmp_path / "dlq.sqlite")
        )
        cb.process(TelemetryPacket(sensor="speed", value=300.0))
        cb.process(TelemetryPacket(sensor="speed", value=None))
        m = cb.metrics
        assert m.total_passed == 1
        assert m.total_rejected == 1
        assert m.state == "CLOSED"
        cb.dlq.close()


# ===================================================================
# Edge Buffer Tests
# ===================================================================
class TestTracksideEdgeBuffer:
    def test_write_and_replay(self, tmp_path):
        buf = TracksideEdgeBuffer(db_path=str(tmp_path / "buf.sqlite"))
        pkt = BufferedPacket(
            packet_id="pkt_001",
            session_id="silverstone_race",
            sensor="speed",
            value=350.0,
        )
        buf.write(pkt)
        rows = buf.replay(session_id="silverstone_race")
        assert len(rows) == 1
        assert rows[0]["packet_id"] == "pkt_001"
        buf.close()

    def test_write_batch(self, tmp_path):
        buf = TracksideEdgeBuffer(db_path=str(tmp_path / "buf.sqlite"))
        packets = [
            BufferedPacket(packet_id=f"pkt_{i}", sensor="rpm", value=12000 + i)
            for i in range(10)
        ]
        inserted = buf.write_batch(packets)
        assert inserted == 10
        assert buf.health.total_buffered == 10
        assert buf.health.pending_sync == 10
        buf.close()

    def test_dedup_on_packet_id(self, tmp_path):
        buf = TracksideEdgeBuffer(db_path=str(tmp_path / "buf.sqlite"))
        pkt = BufferedPacket(packet_id="dup_001", sensor="speed", value=300.0)
        buf.write(pkt)
        buf.write(pkt)  # duplicate
        assert buf.health.total_buffered == 1
        buf.close()

    def test_drain_with_callback(self, tmp_path):
        synced_payloads = []

        def mock_sync(payloads):
            synced_payloads.extend(payloads)
            return True

        buf = TracksideEdgeBuffer(
            db_path=str(tmp_path / "buf.sqlite"),
            sync_callback=mock_sync,
        )
        for i in range(5):
            buf.write(BufferedPacket(packet_id=f"pkt_{i}", sensor="speed", value=float(i)))

        result = buf.drain_pending()
        assert result["synced"] == 5
        assert len(synced_payloads) == 5
        assert buf.health.synced == 5
        assert buf.health.pending_sync == 0
        buf.close()

    def test_drain_failure_marks_failed(self, tmp_path):
        def fail_sync(payloads):
            return False

        buf = TracksideEdgeBuffer(
            db_path=str(tmp_path / "buf.sqlite"),
            sync_callback=fail_sync,
        )
        buf.write(BufferedPacket(packet_id="pkt_001", sensor="speed", value=300.0))
        result = buf.drain_pending()
        assert result["failed"] == 1
        assert buf.health.failed == 1
        buf.close()

    def test_health_metrics(self, tmp_path):
        buf = TracksideEdgeBuffer(
            db_path=str(tmp_path / "buf.sqlite"),
            max_buffer_size=100,
        )
        for i in range(10):
            buf.write(BufferedPacket(packet_id=f"pkt_{i}", sensor="speed", value=float(i)))
        h = buf.health
        assert h.total_buffered == 10
        assert h.pending_sync == 10
        assert h.buffer_utilisation == pytest.approx(0.1, abs=0.01)
        assert h.db_size_bytes > 0
        buf.close()


# ===================================================================
# Geo-Fence Tests
# ===================================================================
class TestGeoFence:
    def test_eu_circuit_scrubs_pii(self):
        geo = GeoFence()
        result = geo.process(
            circuit="barcelona",
            payload={"driver_name": "Max", "speed": 320, "heart_rate": 165},
        )
        assert result.jurisdiction == "EU"
        assert "driver_name" in result.fields_scrubbed
        assert result.local_payload["driver_name"] == "Max"  # local retains full data
        assert result.sync_payload.get("_sync_type") == "metadata_only"

    def test_us_circuit_full_sync(self):
        geo = GeoFence()
        result = geo.process(
            circuit="austin",
            payload={"driver_name": "Max", "speed": 320, "heart_rate": 165},
        )
        assert result.jurisdiction == "US"
        assert len(result.fields_scrubbed) == 0
        assert result.sync_payload["speed"] == 320

    def test_me_circuit_export_control(self):
        geo = GeoFence()
        result = geo.process(
            circuit="yas_marina",
            payload={"speed": 310},
        )
        assert result.jurisdiction == "ME"
        assert result.sync_payload.get("_export_control") is True

    def test_unknown_circuit_defaults_to_us(self):
        geo = GeoFence()
        result = geo.process(
            circuit="unknown_track",
            payload={"speed": 300},
        )
        assert result.jurisdiction == "US"

    def test_biometric_anonymisation(self):
        geo = GeoFence()
        result = geo.process(
            circuit="monza",
            payload={"heart_rate": 165, "speed": 340},
        )
        assert "heart_rate" in result.fields_anonymised
        # Sync payload should have anonymised hash, not original value
        assert result.sync_payload.get("_sync_type") == "metadata_only"
        # Local payload retains original
        assert result.local_payload["heart_rate"] == 165

    def test_compliance_hash_present(self):
        geo = GeoFence()
        result = geo.process(circuit="spielberg", payload={"speed": 310})
        assert len(result.compliance_hash) == 64  # SHA-256

    def test_process_batch(self):
        geo = GeoFence()
        payloads = [{"speed": 300 + i} for i in range(5)]
        results = geo.process_batch("silverstone", payloads)
        assert len(results) == 5
        assert all(r.jurisdiction == "UK" for r in results)

    def test_processing_summary(self):
        geo = GeoFence()
        geo.process("barcelona", {"driver_name": "Test", "speed": 300})
        geo.process("austin", {"speed": 310})
        s = geo.processing_summary
        assert s["total_processed"] == 2
        assert "EU" in s["by_jurisdiction"]
        assert "US" in s["by_jurisdiction"]

    def test_jurisdiction_mapping_covers_calendar(self):
        """Ensure all major 2026 circuits are mapped."""
        key_circuits = [
            "silverstone", "monza", "spa", "austin", "suzuka",
            "barcelona", "spielberg", "monaco",
        ]
        for circuit in key_circuits:
            assert circuit in CIRCUIT_JURISDICTION
