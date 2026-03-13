#!/usr/bin/env python3
"""
Kafka Integration Example
==========================

Demonstrates how to use TracksideEdgeBuffer with Kafka output.

Usage:
    1. Start Kafka locally (docker-compose or standalone)
    2. Install kafka-python: pip install kafka-python
    3. Run: python examples/kafka_integration_example.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.local_persistence import TracksideEdgeBuffer, BufferedPacket


def main():
    print("=== Kafka Integration Example ===\n")

    # Initialize buffer with Kafka enabled
    buffer = TracksideEdgeBuffer(
        db_path="data/example_kafka_buffer.sqlite",
        enable_kafka=True,
        kafka_bootstrap_servers=["localhost:9092"],
        kafka_topic="telemetry-validated",
        kafka_sync_event_topic="telemetry-sync-events",
        kafka_producer_config={"linger_ms": 10, "compression_type": "lz4"},
    )

    print("Buffer initialized with Kafka output enabled")
    print(f"Kafka enabled: {buffer.enable_kafka}\n")

    # Write some test packets
    packets = [
        BufferedPacket(
            session_id="test_session_1",
            sensor="engine_temp",
            value=95.5,
            metadata={"circuit": "monaco", "lap": 12},
        ),
        BufferedPacket(
            session_id="test_session_1",
            sensor="tyre_pressure_fl",
            value=2.1,
            metadata={"circuit": "monaco", "lap": 12},
        ),
        BufferedPacket(
            session_id="test_session_1",
            sensor="brake_temp_fr",
            value=350.0,
            metadata={"circuit": "monaco", "lap": 12},
        ),
    ]

    print("Writing 3 test packets...")
    for pkt in packets:
        buffer.write(pkt)
    
    buffer.flush()  # Force commit
    print("Packets written to SQLite and sent to Kafka\n")

    # Check stats
    health = buffer.health
    kafka_stats = buffer.kafka_stats

    print("Buffer Health:")
    print(f"  Total buffered: {health.total_buffered}")
    print(f"  Pending sync: {health.pending_sync}")
    print(f"  DB size: {health.db_size_bytes} bytes")
    
    print("\nKafka Stats:")
    print(f"  Messages sent: {kafka_stats['sent']}")
    print(f"  Messages failed: {kafka_stats['failed']}")
    print(f"  Avg ACK latency: {kafka_stats['avg_latency_ms']} ms")
    print(f"  Sent by topic: {kafka_stats['sent_by_topic']}")

    # Clean up
    buffer.close()
    print("\nBuffer closed successfully")

    print("\nNext steps:")
    print("  1. Check validated topic: kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetry-validated --from-beginning")
    print("  2. Check sync events: kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetry-sync-events --from-beginning")
    print("  3. Check SQLite: sqlite3 data/example_kafka_buffer.sqlite 'SELECT * FROM telemetry_buffer;'")


if __name__ == "__main__":
    main()
