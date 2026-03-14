#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# See LICENSE for full details.

"""
DLQ Kafka 3-Stream Routing Example
====================================
Developed for the 2026 Telemetry Platform Initiative.

Demonstrates how the Dead Letter Queue (DLQ) routes rejected telemetry
packets to three distinct Kafka topics based on reprocessing outcome:

    ┌──────────────────────────────────────────────────────────────────┐
    │                   Circuit Breaker rejects pkt                    │
    │                              │                                   │
    │                     enqueue() called                             │
    │                              │                                   │
    │                    ─────────────────────                         │
    │                    ▼                                             │
    │             dlq-repairable  ← packet quarantined, eligible for   │
    │                                reprocessing (retry_count < 3)    │
    │                                                                  │
    │         Reprocessing loop runs (_finalise_report)                │
    │                    │                                             │
    │         ┌──────────┴──────────┐                                  │
    │         ▼                     ▼                                  │
    │    Repair succeeds        Repair fails                           │
    │         │                     │                                  │
    │  dlq-repaired          retry_count >= 3?                         │
    │                         │           │                            │
    │                        yes          no                           │
    │                         │           │                            │
    │              dlq-non-repairable  dlq-repairable (re-published)   │
    └──────────────────────────────────────────────────────────────────┘

Prerequisites
-------------
    pip install kafka-python

    # Start a local Kafka broker (Docker):
    docker run -d --name kafka -p 9092:9092 \\
        -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \\
        -e KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092 \\
        -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \\
        confluentinc/cp-kafka:latest

Usage
-----
    PYTHONPATH="." python examples/dlq_kafka_routing_example.py

    # Or from the GPU stress test:
    PYTHONPATH="." python tools/telemetry_gpu_stress_test.py \\
        --enable-kafka --kafka-servers localhost:9092
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.circuit_breaker import TelemetryCircuitBreaker, TelemetryPacket

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
KAFKA_BROKERS = ["localhost:9092"]

TOPIC_REPAIRABLE = "dlq-repairable"
TOPIC_REPAIRED = "dlq-repaired"
TOPIC_NON_REPAIRABLE = "dlq-non-repairable"

# ---------------------------------------------------------------------------
# Helper — build a synthetic bad packet
# ---------------------------------------------------------------------------


def bad_packet(sensor: str = "engine_temp_c", value: object = "NOT_A_NUMBER") -> TelemetryPacket:
    """Create a telemetry packet that will fail schema validation."""
    return TelemetryPacket(
        packet_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow().isoformat(),
        sensor=sensor,
        value=value,
        metadata={"source": "dlq_kafka_routing_example"},
    )


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("  DLQ Kafka 3-Stream Routing Demo")
    print("  Telemetry Platform 2026 — Resilient RAP Framework")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Instantiate the circuit breaker with Kafka routing enabled.
    #    The DLQ will publish each quarantined packet to `dlq-repairable`
    #    as soon as enqueue() is called.
    # ------------------------------------------------------------------
    print("\n[1] Creating TelemetryCircuitBreaker with Kafka DLQ routing...")
    breaker = TelemetryCircuitBreaker(
        failure_threshold=3,
        recovery_timeout=5.0,
        dlq_path="data/dlq_kafka_demo.sqlite",
        enable_kafka=True,
        kafka_bootstrap_servers=KAFKA_BROKERS,
        kafka_topic_repairable=TOPIC_REPAIRABLE,
        kafka_topic_repaired=TOPIC_REPAIRED,
        kafka_topic_non_repairable=TOPIC_NON_REPAIRABLE,
    )
    print(f"    Kafka enabled on DLQ: {breaker.dlq.enable_kafka}")
    print(f"    Topics: {TOPIC_REPAIRABLE} | {TOPIC_REPAIRED} | {TOPIC_NON_REPAIRABLE}")

    # ------------------------------------------------------------------
    # 2. Inject packets that will fail validation and land in the DLQ.
    #    Each rejected packet is automatically published to dlq-repairable.
    # ------------------------------------------------------------------
    print("\n[2] Sending 5 invalid packets through the circuit breaker...")
    bad_packets = [
        bad_packet("engine_temp_c", "NOT_A_NUMBER"),           # string in numeric field
        bad_packet("brake_temp_c", 9999.0),                    # out-of-range value
        bad_packet("engine_temp_c_new", 95.0),                 # schema drift (_new suffix)
        bad_packet("throttle_pct", -5.0),                      # below minimum
        bad_packet("speed_kmh", "fast"),                       # string in numeric field
    ]
    for pkt in bad_packets:
        accepted, reason = breaker.process(pkt)
        status = "✓ accepted" if accepted else f"✗ rejected ({reason})"
        print(f"    {pkt.sensor}: {status}")

    print(f"\n    DLQ depth: {breaker.dlq.depth()} packets")
    if breaker.dlq.enable_kafka:
        print(
            f"    Kafka stats: {breaker.dlq.kafka_stats} "
            f"(published to '{TOPIC_REPAIRABLE}')"
        )

    # ------------------------------------------------------------------
    # 3. Simulate the reprocessing loop — mirrors _finalise_report().
    #    After each repair attempt publish_repair_outcome() is called to
    #    route the result to the correct Kafka topic.
    # ------------------------------------------------------------------
    print("\n[3] Running DLQ reprocessing loop...")
    candidates = breaker.dlq.fetch_reprocessable(limit=10)
    repaired = still_bad = max_retries_hit = 0

    for rec in candidates:
        raw_value = rec.get("value")
        # Attempt a simple string-to-float repair
        repaired_ok = False
        if isinstance(raw_value, str):
            try:
                float(raw_value.strip())
                repaired_ok = True
            except ValueError:
                pass

        if repaired_ok:
            breaker.dlq.mark_reprocessed(rec["packet_id"])
            breaker.dlq.publish_repair_outcome(rec, "repaired")
            print(f"    ✓ repaired  → '{TOPIC_REPAIRED}'   [{rec['packet_id'][:8]}…]")
            repaired += 1
        else:
            breaker.dlq.increment_retry(rec["packet_id"])
            retry_count = rec.get("retry_count", 0) + 1
            if retry_count >= 3:
                breaker.dlq.publish_repair_outcome(rec, "non_repairable")
                print(
                    f"    ✗ dead-end  → '{TOPIC_NON_REPAIRABLE}' [{rec['packet_id'][:8]}…]"
                )
                max_retries_hit += 1
            else:
                breaker.dlq.publish_repair_outcome(rec, "repairable")
                print(
                    f"    ↺ retry #{retry_count}  → '{TOPIC_REPAIRABLE}'  [{rec['packet_id'][:8]}…]"
                )
                still_bad += 1

    print("\n[4] Reprocessing summary:")
    print(f"    repaired        : {repaired}")
    print(f"    still repairable: {still_bad}")
    print(f"    non-repairable  : {max_retries_hit}")
    if breaker.dlq.enable_kafka:
        print(f"    Kafka stats     : {breaker.dlq.kafka_stats}")

    # ------------------------------------------------------------------
    # 4. Use the GPU stress test with Kafka enabled (CLI shortcut).
    # ------------------------------------------------------------------
    print("\n[5] To run the full GPU stress test with Kafka DLQ routing:")
    print(
        "    PYTHONPATH='.' python tools/telemetry_gpu_stress_test.py "
        "--enable-kafka --kafka-servers localhost:9092"
    )

    breaker.dlq.close()
    print("\nDemo complete. ✓")


if __name__ == "__main__":
    main()
