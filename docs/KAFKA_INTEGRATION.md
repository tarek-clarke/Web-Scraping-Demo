# Kafka Integration Guide

## Overview

The `TracksideEdgeBuffer` now supports optional Kafka output alongside the existing SQLite persistence. This enables real-time streaming of validated telemetry packets to downstream consumers while maintaining the local-first architecture for trackside resilience.

## Architecture

```
Car RF Downlink
    │
    ▼
Circuit Breaker ──────► SQLite Edge Buffer (local-first, crash-safe)
    │                          │
    │                          ├──► Kafka Topic (real-time stream)
    │                          └──► Background drain to cloud sink
    │
    └──► DLQ ─────────────────► Kafka DLQ Topic (quarantined packets)
```

## Key Design Principles

1. **Local-first**: SQLite write always succeeds, even if Kafka fails
2. **Non-blocking**: Kafka sends are async/fire-and-forget
3. **Dual output**: SQLite for reliability, Kafka for real-time streaming
4. **Optional**: Kafka can be disabled without breaking existing functionality

## Installation

Install the optional Kafka dependency:

```bash
pip install kafka-python==2.0.2
```

## Configuration

### Basic Setup

```python
from src.local_persistence import TracksideEdgeBuffer, BufferedPacket

buffer = TracksideEdgeBuffer(
    db_path="data/edge_buffer.sqlite",
    enable_kafka=True,
    kafka_bootstrap_servers=["localhost:9092"],
    kafka_topic="telemetry-validated",
    kafka_dlq_topic="telemetry-dlq",
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_kafka` | bool | False | Enable Kafka output |
| `kafka_bootstrap_servers` | List[str] | None | Kafka broker addresses |
| `kafka_topic` | str | "telemetry-validated" | Topic for validated packets |
| `kafka_dlq_topic` | str | "telemetry-dlq" | Topic for DLQ packets |

## Usage

### Write Packets

```python
packet = BufferedPacket(
    session_id="monaco_fp1",
    sensor="engine_temp",
    value=95.5,
    metadata={"lap": 12, "driver": "44"}
)

# Writes to both SQLite and Kafka (if enabled)
buffer.write(packet)
```

### Batch Writes

```python
packets = [
    BufferedPacket(session_id="session1", sensor="engine_temp", value=95.5),
    BufferedPacket(session_id="session1", sensor="tyre_pressure_fl", value=2.1),
]

# Both SQLite and Kafka writes are batched
buffer.write_batch(packets)
```

### Monitor Kafka Stats

```python
stats = buffer.kafka_stats
print(f"Kafka messages sent: {stats['sent']}")
print(f"Kafka messages failed: {stats['failed']}")
```

### Health Check

```python
health = buffer.health
print(f"Total buffered: {health.total_buffered}")
print(f"Connectivity: {health.connectivity}")
```

## Kafka Message Format

### Validated Telemetry (telemetry-validated topic)

```json
{
  "packet_id": "a1b2c3d4e5f6",
  "session_id": "monaco_fp1",
  "timestamp": "2026-03-04T15:30:45.123456",
  "sensor": "engine_temp",
  "value": 95.5,
  "metadata": {"lap": 12, "driver": "44"},
  "sync_status": "PENDING"
}
```

### DLQ Packets (telemetry-dlq topic)

Same format as validated packets, but these represent quarantined/failed packets from the circuit breaker.

## Kafka Consumer Example

Subscribe to validated telemetry:

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'telemetry-validated',
    bootstrap_servers=['localhost:9092'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
)

for message in consumer:
    packet = message.value
    print(f"Sensor: {packet['sensor']}, Value: {packet['value']}")
```

## Production Deployment

### Docker Compose Example

```yaml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  telemetry-buffer:
    build: .
    depends_on:
      - kafka
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      ENABLE_KAFKA: "true"
```

### Environment Variables

```bash
export KAFKA_BOOTSTRAP_SERVERS="kafka1:9092,kafka2:9092,kafka3:9092"
export KAFKA_TOPIC="telemetry-validated"
export KAFKA_DLQ_TOPIC="telemetry-dlq"
export ENABLE_KAFKA="true"
```

## Error Handling

### Kafka Unavailable

If Kafka is unavailable at startup:
- Buffer initialization succeeds (falls back to SQLite-only mode)
- Logs warning: "Kafka requested but connection failed"
- `enable_kafka` is automatically set to `False`
- All packets continue to be written to SQLite

### Kafka Send Failures

If Kafka send fails during runtime:
- SQLite write still succeeds (local-first guarantee)
- Failed send is logged with callback
- `kafka_stats['failed']` counter increments
- System continues operating normally

## Performance Considerations

### Throughput

- SQLite writes: ~1.3 µs/packet (C++ optimized path)
- Kafka sends: ~0.5-2 ms/packet (async, non-blocking)
- **Kafka does not block SQLite writes**

### Latency

- SQLite write latency: <1 ms p95
- Kafka adds: 0-5 ms (async callback time)
- Total pipeline latency: still sub-millisecond p95

### Backpressure

Kafka producer has built-in backpressure:
- `max_in_flight_requests_per_connection=5`
- `acks='all'` (wait for all replicas)
- `retries=3` (automatic retry on transient failures)

## Monitoring

### Kafka Metrics to Track

1. **Messages sent/failed** (`buffer.kafka_stats`)
2. **Kafka producer lag** (via JMX or Kafka monitoring tools)
3. **Consumer lag** (downstream applications)
4. **Disk usage** (Kafka log retention)

### Alerts

Set up alerts for:
- `kafka_stats['failed'] / kafka_stats['sent'] > 0.05` (5% failure rate)
- Kafka consumer lag > 1000 messages
- Kafka broker offline

## Troubleshooting

### Issue: Kafka messages not appearing

**Check:**
1. Kafka broker is running: `docker ps | grep kafka`
2. Topic exists: `kafka-topics --list --bootstrap-server localhost:9092`
3. Buffer has Kafka enabled: `print(buffer.enable_kafka)`

### Issue: High Kafka failure rate

**Possible causes:**
1. Kafka broker overloaded
2. Network connectivity issues
3. Topic partition count too low

**Fix:**
1. Scale Kafka brokers horizontally
2. Increase topic partitions: `kafka-topics --alter --topic telemetry-validated --partitions 10`
3. Check network latency between buffer and Kafka

## Migration Path

### Phase 1: Shadow Mode (Week 1-2)
- Enable Kafka in production
- Monitor dual-write success rate
- Don't consume from Kafka yet (SQLite-only consumers)

### Phase 2: Parallel Validation (Week 3-4)
- Add Kafka consumers alongside SQLite readers
- Compare data consistency
- Measure end-to-end latency

### Phase 3: Primary Kafka (Week 5+)
- Shift primary consumers to Kafka
- Keep SQLite for local replay/forensics
- Reduce SQLite retention (7 days → 24 hours)

## See Also

- [Local Persistence Documentation](../src/local_persistence.py)
- [Circuit Breaker Integration](../src/circuit_breaker.py)
- [Example: Kafka Integration](../examples/kafka_integration_example.py)
- [ADR-001: SQLite WAL over Redis](adr/001-sqlite-wal-over-redis.md)
