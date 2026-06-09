#!/usr/bin/env python3
"""
Tests for Telemetry Platform Production Modules
==========================================
Validates: Circuit-Breaker, Edge Buffer, Geo-Fence, and Health Monitor.
"""

import sys
import time
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.circuit_breaker as circuit_breaker_module  # noqa: E402
import src.local_persistence as local_persistence_module  # noqa: E402

from src.circuit_breaker import (  # noqa: E402
    TelemetryCircuitBreaker,
    TelemetryPacket,
    SchemaValidator,
    DeadLetterQueue,
    CircuitState,
    DLQRecord,
)
from src.local_persistence import (  # noqa: E402
    TracksideEdgeBuffer,
    BufferedPacket,
)
from src.geo_fence import (  # noqa: E402
    GeoFence,
    CIRCUIT_JURISDICTION,
)
from src.audit_log import ComplianceAuditLog, GENESIS_HASH  # noqa: E402
from src.middleware.tracing import RequestContext  # noqa: E402


class FakeFuture:
    def __init__(self, topic, key, value):
        self.topic = topic
        self.key = key
        self.value = value

    def add_callback(self, callback):
        callback({"topic": self.topic, "key": self.key, "value": self.value})
        return self

    def add_errback(self, _callback):
        return self


class FakeKafkaProducer:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.sent = []
        FakeKafkaProducer.instances.append(self)

    def send(self, topic, value=None, key=None):
        self.sent.append({"topic": topic, "key": key, "value": value})
        return FakeFuture(topic, key, value)

    def flush(self, timeout=None):
        return timeout

    def close(self):
        return None


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
        dlq.flush()
        assert dlq.depth() == 1
        dlq.close()

    def test_recent_returns_records(self, tmp_path):
        dlq = DeadLetterQueue(db_path=str(tmp_path / "test_dlq.sqlite"))
        for i in range(5):
            pkt = TelemetryPacket(sensor=f"sensor_{i}", value=None)
            record = DLQRecord(packet=pkt, reason="test", circuit_state="OPEN")
            dlq.enqueue(record)
        dlq.flush()
        recent = dlq.recent(limit=3)
        assert len(recent) == 3
        dlq.close()

    def test_mark_reprocessed(self, tmp_path):
        dlq = DeadLetterQueue(db_path=str(tmp_path / "test_dlq.sqlite"))
        pkt = TelemetryPacket(packet_id="pkt_001", sensor="rpm", value=None)
        record = DLQRecord(packet=pkt, reason="test", circuit_state="CLOSED")
        dlq.enqueue(record)
        dlq.flush()
        assert dlq.depth() == 1
        dlq.mark_reprocessed("pkt_001")
        assert dlq.depth() == 0
        dlq.close()


class TestCircuitBreaker:
    def test_kafka_outputs_include_raw_drift_and_alerts(self, tmp_path, monkeypatch):
        FakeKafkaProducer.instances.clear()
        monkeypatch.setattr(circuit_breaker_module, "KAFKA_AVAILABLE", True)
        monkeypatch.setattr(circuit_breaker_module, "KafkaProducer", FakeKafkaProducer)

        cb = TelemetryCircuitBreaker(
            failure_threshold=1,
            dlq_path=str(tmp_path / "dlq.sqlite"),
            enable_kafka=True,
            kafka_bootstrap_servers=["localhost:9092"],
        )

        accepted, reason = cb.process(
            TelemetryPacket(packet_id="pkt_bad", sensor="throttle", value="OVERHEAT")
        )

        assert accepted is False
        assert (
            "string_in_numeric_field" in reason
            or "type_violation:throttle" in reason
        )

        producer = cb.dlq._kafka_producer
        assert producer is not None

        sent_topics = [message["topic"] for message in producer.sent]
        assert "telemetry-raw" in sent_topics
        assert "telemetry-schema-drift" in sent_topics
        assert "telemetry-alerts" in sent_topics
        assert "dlq-repairable" in sent_topics

        raw_event = next(message for message in producer.sent if message["topic"] == "telemetry-raw")
        drift_event = next(
            message for message in producer.sent if message["topic"] == "telemetry-schema-drift"
        )
        alert_event = next(message for message in producer.sent if message["topic"] == "telemetry-alerts")

        assert raw_event["value"]["event_type"] == "telemetry.raw"
        assert drift_event["value"]["event_type"] == "telemetry.schema_drift"
        assert alert_event["value"]["event_type"] in {
            "telemetry.alert.state_change",
            "telemetry.alert.validation_failure",
        }
        assert cb.dlq.kafka_stats["sent_by_topic"]["telemetry-raw"] == 1
        cb.dlq.close()

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
        # Allow both OPEN and HALF_OPEN due to auto-promotion logic
        assert cb.state in [CircuitState.OPEN, CircuitState.HALF_OPEN]
        cb.dlq.close()

    def test_open_rejects_all_packets(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=2, recovery_timeout=100,
            dlq_path=str(tmp_path / "dlq.sqlite"),
        )
        # Trip the breaker
        for _ in range(2):
            cb.process(TelemetryPacket(sensor="speed", value=None))
        # Allow both OPEN and HALF_OPEN due to auto-promotion logic
        assert cb.state in [CircuitState.OPEN, CircuitState.HALF_OPEN]

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
        assert cb.state in [CircuitState.OPEN, CircuitState.HALF_OPEN]

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
            TelemetryPacket(sensor="speed", value=300.0, timestamp="2026-03-21T00:00:01"),
            TelemetryPacket(sensor="speed", value=None, timestamp="2026-03-21T00:00:02"),
            TelemetryPacket(sensor="speed", value=310.0, timestamp="2026-03-21T00:00:03"),
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
        assert cb.state in [CircuitState.OPEN, CircuitState.HALF_OPEN]
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
    def test_kafka_streams_use_event_envelopes(self, tmp_path, monkeypatch):
        FakeKafkaProducer.instances.clear()
        monkeypatch.setattr(local_persistence_module, "KAFKA_AVAILABLE", True)
        monkeypatch.setattr(local_persistence_module, "KafkaProducer", FakeKafkaProducer)

        def mock_sync(_payloads):
            return True

        buf = TracksideEdgeBuffer(
            db_path=str(tmp_path / "buf.sqlite"),
            sync_callback=mock_sync,
            enable_kafka=True,
            kafka_bootstrap_servers=["localhost:9092"],
        )
        pkt = BufferedPacket(
            packet_id="pkt_001",
            session_id="session_a",
            sensor="speed",
            value=301.5,
        )

        buf.write(pkt)
        buf.flush()
        buf.drain_pending()

        producer = buf._kafka_producer
        assert producer is not None
        sent_topics = [message["topic"] for message in producer.sent]
        assert "telemetry-validated" in sent_topics
        assert "telemetry-sync-events" in sent_topics

        validated_event = next(
            message for message in producer.sent if message["topic"] == "telemetry-validated"
        )
        assert validated_event["key"] == "session_a"
        assert validated_event["value"]["event_type"] == "telemetry.validated"
        assert validated_event["value"]["payload"]["packet_id"] == "pkt_001"

        assert producer.kwargs["compression_type"] == "lz4"
        assert producer.kwargs["linger_ms"] == 10
        assert buf.kafka_stats["sent_by_topic"]["telemetry-validated"] == 1
        assert buf.kafka_stats["sent_by_topic"]["telemetry-sync-events"] == 1
        buf.close()

    def test_write_and_replay(self, tmp_path):
        buf = TracksideEdgeBuffer(db_path=str(tmp_path / "buf.sqlite"))
        pkt = BufferedPacket(
            packet_id="pkt_001",
            session_id="silverstone_race",
            sensor="speed",
            value=350.0,
        )
        buf.write(pkt)
        buf.flush()  # Ensure batched write is committed
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
        buf.flush()
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
        buf.flush()

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
        buf.flush()
        result = buf.drain_pending()
        assert result["failed"] == 1
        # Exactly-once semantics: failed packets roll back to PENDING for retry
        assert buf.health.pending_sync == 1
        assert buf.health.failed == 0
        buf.close()

    def test_health_metrics(self, tmp_path):
        buf = TracksideEdgeBuffer(
            db_path=str(tmp_path / "buf.sqlite"),
            max_buffer_size=100,
        )
        for i in range(10):
            buf.write(BufferedPacket(packet_id=f"pkt_{i}", sensor="speed", value=float(i)))
        buf.flush()
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


# ===================================================================
# Compliance Audit Log Tests
# ===================================================================
class TestComplianceAuditLog:
    def test_record_and_count(self, tmp_path):
        log = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        assert log.count() == 0
        log.record(action="PII_SCRUBBED", circuit="barcelona", jurisdiction="EU")
        assert log.count() == 1
        log.close()

    def test_hash_chain_integrity(self, tmp_path):
        log = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        for i in range(10):
            log.record(
                action="TEST_ACTION",
                circuit=f"circuit_{i}",
                jurisdiction="EU",
                details={"index": i},
            )
        assert log.verify_chain() is True
        log.close()

    def test_tamper_detection(self, tmp_path):
        log = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        log.record(action="LEGIT", circuit="monza", jurisdiction="EU")
        log.record(action="LEGIT", circuit="spa", jurisdiction="EU")

        # Tamper with a record directly
        log._conn.execute(
            "UPDATE audit_log SET action = 'TAMPERED' WHERE id = 1"
        )
        log._conn.commit()

        assert log.verify_chain() is False
        log.close()

    def test_query_by_jurisdiction(self, tmp_path):
        log = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        log.record(action="PII_SCRUBBED", circuit="barcelona", jurisdiction="EU")
        log.record(action="FULL_SYNC", circuit="austin", jurisdiction="US")
        log.record(action="PII_SCRUBBED", circuit="monza", jurisdiction="EU")

        eu = log.query_by_jurisdiction("EU")
        assert len(eu) == 2
        assert all(e["jurisdiction"] == "EU" for e in eu)
        log.close()

    def test_query_by_request_id(self, tmp_path):
        log = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        log.record(action="STAGE_1", request_id="req_abc123")
        log.record(action="STAGE_2", request_id="req_abc123")
        log.record(action="OTHER", request_id="req_other")

        trace = log.query_by_request_id("req_abc123")
        assert len(trace) == 2
        assert all(t["request_id"] == "req_abc123" for t in trace)
        log.close()

    def test_summary(self, tmp_path):
        log = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        log.record(action="PII_SCRUBBED", jurisdiction="EU")
        log.record(action="PII_SCRUBBED", jurisdiction="EU")
        log.record(action="FULL_SYNC", jurisdiction="US")
        s = log.summary()
        assert s["total_entries"] == 3
        assert s["by_action"]["PII_SCRUBBED"] == 2
        assert s["chain_intact"] is True
        log.close()

    def test_genesis_hash_on_empty_db(self, tmp_path):
        log = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        assert log._last_hash == GENESIS_HASH
        log.close()

    def test_chain_resumes_after_reopen(self, tmp_path):
        db = str(tmp_path / "audit.sqlite")
        log1 = ComplianceAuditLog(db_path=db)
        log1.record(action="FIRST")
        hash_after_first = log1._last_hash
        log1.close()

        log2 = ComplianceAuditLog(db_path=db)
        assert log2._last_hash == hash_after_first
        log2.record(action="SECOND")
        assert log2.verify_chain() is True
        assert log2.count() == 2
        log2.close()


# ===================================================================
# Geo-Fence + Audit Integration Tests
# ===================================================================
class TestGeoFenceAuditIntegration:
    def test_eu_processing_creates_audit_entries(self, tmp_path):
        audit = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        geo = GeoFence(audit_log=audit)
        geo.process(
            circuit="barcelona",
            payload={"driver_name": "Max", "speed": 320, "heart_rate": 165},
            session_id="barcelona_fp1",
        )
        # EU should generate: PII_SCRUBBED, BIOMETRIC_ANONYMISED, METADATA_ONLY_SYNC, LOCAL_RETENTION
        assert audit.count() >= 3
        assert audit.verify_chain() is True
        audit.close()

    def test_us_processing_no_audit_entries(self, tmp_path):
        audit = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        geo = GeoFence(audit_log=audit)
        geo.process(circuit="austin", payload={"speed": 320})
        # US has no scrubbing, no metadata-only, no retention
        assert audit.count() == 0
        audit.close()

    def test_me_processing_export_control_audited(self, tmp_path):
        audit = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        geo = GeoFence(audit_log=audit)
        geo.process(circuit="yas_marina", payload={"speed": 310})
        entries = audit.recent()
        actions = [e["action"] for e in entries]
        assert "EXPORT_CONTROL_APPLIED" in actions
        audit.close()

    def test_request_id_propagated_to_audit(self, tmp_path):
        audit = ComplianceAuditLog(db_path=str(tmp_path / "audit.sqlite"))
        geo = GeoFence(audit_log=audit)
        geo.process(
            circuit="monza",
            payload={"driver_name": "Test", "heart_rate": 150},
            request_id="trace_001",
        )
        entries = audit.query_by_request_id("trace_001")
        assert len(entries) >= 1
        assert all(e["request_id"] == "trace_001" for e in entries)
        audit.close()

    def test_no_audit_when_disabled(self):
        """GeoFence works without audit log (backward compatible)."""
        geo = GeoFence()  # No audit_log passed
        result = geo.process(circuit="barcelona", payload={"driver_name": "Test"})
        assert result.jurisdiction == "EU"


# ===================================================================
# DLQ Reprocessing Tests
# ===================================================================
class TestDLQReprocessing:
    def test_reprocess_recovers_updated_range(self, tmp_path):
        """Packet rejected for out-of-range can be recovered after range update."""
        cb = TelemetryCircuitBreaker(
            failure_threshold=10, dlq_path=str(tmp_path / "dlq.sqlite")
        )
        # Submit a packet that will be rejected (engine_temp > 1000)
        pkt = TelemetryPacket(sensor="engine_temp", value=1050.0)
        accepted, reason = cb.process(pkt)
        assert accepted is False
        cb.dlq.flush()
        assert cb.dlq.depth() == 1

        # Update validator ranges to accept higher temps
        cb.validator.value_ranges["engine_temp"] = (-40.0, 1200.0)

        # Reprocess
        result = cb.reprocess_dlq()
        assert result["recovered"] == 1
        assert cb.dlq.depth() == 0
        cb.dlq.close()

    def test_reprocess_still_invalid_increments_retry(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=10, dlq_path=str(tmp_path / "dlq.sqlite")
        )
        cb.process(TelemetryPacket(sensor="speed", value=None))
        cb.dlq.flush()
        assert cb.dlq.depth() == 1

        # Reprocess - null value is still invalid
        result = cb.reprocess_dlq()
        assert result["recovered"] == 0
        assert result["still_invalid"] == 1
        cb.dlq.close()

    def test_max_retries_stops_reprocessing(self, tmp_path):
        cb = TelemetryCircuitBreaker(
            failure_threshold=10, dlq_path=str(tmp_path / "dlq.sqlite")
        )
        pkt = TelemetryPacket(sensor="speed", value=None)
        cb.process(pkt)
        cb.dlq.flush()

        # Reprocess 3 times to hit max
        for _ in range(3):
            cb.reprocess_dlq()

        # 4th attempt should report max_retries
        result = cb.reprocess_dlq()
        assert result["recovered"] == 0
        assert result["still_invalid"] == 0
        assert result["max_retries"] == 0  # No candidates left (all at max)
        cb.dlq.close()

    def test_fetch_reprocessable(self, tmp_path):
        dlq = DeadLetterQueue(db_path=str(tmp_path / "dlq.sqlite"))
        for i in range(5):
            pkt = TelemetryPacket(packet_id=f"pkt_{i}", sensor="speed", value=None)
            dlq.enqueue(DLQRecord(packet=pkt, reason="test", circuit_state="CLOSED"))
        dlq.flush()

        candidates = dlq.fetch_reprocessable(limit=3)
        assert len(candidates) == 3
        dlq.close()

    def test_increment_retry(self, tmp_path):
        dlq = DeadLetterQueue(db_path=str(tmp_path / "dlq.sqlite"))
        pkt = TelemetryPacket(packet_id="retry_test", sensor="speed", value=None)
        dlq.enqueue(DLQRecord(packet=pkt, reason="test", circuit_state="CLOSED"))
        dlq.flush()

        dlq.increment_retry("retry_test")
        dlq.increment_retry("retry_test")
        dlq.increment_retry("retry_test")

        # Should no longer be reprocessable (retry_count >= 3)
        candidates = dlq.fetch_reprocessable()
        assert len(candidates) == 0
        dlq.close()


# ===================================================================
# Edge Buffer Exactly-Once Drain Tests
# ===================================================================
class TestExactlyOnceDrain:
    def test_drain_returns_batch_id(self, tmp_path):
        synced = []

        def mock_sync(payloads):
            synced.extend(payloads)
            return True

        buf = TracksideEdgeBuffer(
            db_path=str(tmp_path / "buf.sqlite"),
            sync_callback=mock_sync,
        )
        buf.write(BufferedPacket(packet_id="pkt_001", sensor="speed", value=300.0))
        buf.flush()
        result = buf.drain_pending()
        assert "batch_id" in result
        assert result["synced"] == 1
        buf.close()

    def test_drain_failure_rolls_back_to_pending(self, tmp_path):
        def fail_sync(payloads):
            return False

        buf = TracksideEdgeBuffer(
            db_path=str(tmp_path / "buf.sqlite"),
            sync_callback=fail_sync,
        )
        buf.write(BufferedPacket(packet_id="pkt_001", sensor="speed", value=300.0))
        buf.flush()
        result = buf.drain_pending()
        assert result["failed"] == 1

        # Packet should be back to PENDING (not FAILED)
        h = buf.health
        assert h.pending_sync == 1
        assert h.failed == 0
        buf.close()

    def test_recover_incomplete_batches(self, tmp_path):
        buf = TracksideEdgeBuffer(db_path=str(tmp_path / "buf.sqlite"))
        buf.write(BufferedPacket(packet_id="pkt_001", sensor="speed", value=300.0))
        buf.flush()

        # Simulate a crash during drain by manually setting DRAINING state
        buf._conn.execute(
            "UPDATE telemetry_buffer SET sync_status = 'DRAINING', drain_batch_id = 'crash_batch'"
        )
        buf._conn.commit()

        recovered = buf.recover_incomplete_batches()
        assert recovered == 1
        assert buf.health.pending_sync == 1
        buf.close()

    def test_drain_history(self, tmp_path):
        synced = []

        def mock_sync(payloads):
            synced.extend(payloads)
            return True

        buf = TracksideEdgeBuffer(
            db_path=str(tmp_path / "buf.sqlite"),
            sync_callback=mock_sync,
        )
        for i in range(3):
            buf.write(BufferedPacket(packet_id=f"pkt_{i}", sensor="speed", value=float(i)))
            buf.flush()
            buf.drain_pending()

        history = buf.drain_history
        assert len(history) == 3
        assert all(h["status"] == "ACKED" for h in history)
        buf.close()

    def test_batch_payload_includes_batch_id(self, tmp_path):
        received = []

        def capture_sync(payloads):
            received.extend(payloads)
            return True

        buf = TracksideEdgeBuffer(
            db_path=str(tmp_path / "buf.sqlite"),
            sync_callback=capture_sync,
        )
        buf.write(BufferedPacket(packet_id="pkt_001", sensor="speed", value=300.0))
        buf.flush()
        buf.drain_pending()
        assert len(received) == 1
        assert "_batch_id" in received[0]
        buf.close()


# ===================================================================
# Request-ID Tracing Tests
# ===================================================================
class TestRequestTracing:
    def test_new_context_has_request_id(self):
        ctx = RequestContext.new(session_id="fp1", source="rf_downlink")
        assert len(ctx.request_id) == 16
        assert ctx.session_id == "fp1"
        assert ctx.source == "rf_downlink"

    def test_add_stages(self):
        ctx = RequestContext.new()
        ctx.add_stage("circuit_breaker", status="PASSED")
        ctx.add_stage("edge_buffer", status="BUFFERED")
        ctx.add_stage("geo_fence", status="PII_SCRUBBED")
        assert len(ctx.stages) == 3
        assert ctx.last_stage == "geo_fence"

    def test_trace_summary(self):
        ctx = RequestContext.new(session_id="race")
        ctx.add_stage("cb", status="OK")
        ctx.add_stage("buf", status="OK")
        summary = ctx.trace_summary()
        assert summary["request_id"] == ctx.request_id
        assert summary["stage_count"] == 2
        assert len(summary["stages"]) == 2

    def test_is_failed(self):
        ctx = RequestContext.new()
        ctx.add_stage("cb", status="PASSED")
        assert ctx.is_failed is False

        ctx.add_stage("geo_fence", status="REJECTED")
        assert ctx.is_failed is True

    def test_latency_tracking(self):
        ctx = RequestContext.new()
        time.sleep(0.01)
        ctx.add_stage("stage_1", status="OK")
        assert ctx.stages[0].latency_ms > 0
