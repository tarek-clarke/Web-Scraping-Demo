# Operations & Failure Runbook - Telemetry Platform Telemetry Spine

## Recovery Objectives

| Metric | Target | Mechanism |
|--------|--------|-----------|
| **RPO** (Recovery Point Objective) | **0 packets lost** | SQLite WAL local persistence - every packet is committed to disk before any cloud sync is attempted |
| **RTO** (Recovery Time Objective) | **< 5 seconds** | Background drain thread auto-resumes on process restart; incomplete batches are auto-recovered |
| **MTTR** (Mean Time to Repair) | **< 30 seconds** | Circuit breaker auto-heals via HALF_OPEN probing after configurable cooldown |

---

## Failure Scenarios

### 1. Cloud Uplink Loss (Connectivity Drop)

**Symptom**: `sync_callback` returns `False` or raises an exception.

**Automatic Response**:
- Edge buffer continues accepting writes locally (SQLite WAL).
- Drain batches are rolled back from DRAINING to PENDING.
- Background drain retries every 5 seconds (configurable).
- Buffer can hold 100,000+ packets before back-pressure warning.

**Manual Override**:
```bash
# Check buffer health
python -c "
from src.local_persistence import TracksideEdgeBuffer
buf = TracksideEdgeBuffer()
print(buf.health)
"
```

**Recovery**: When connectivity restores, the background drain automatically syncs all pending packets with exactly-once batch semantics.

---

### 2. Corrupted Telemetry Burst (Sensor Fault / Bit-Flip)

**Symptom**: Multiple packets fail SchemaValidator range checks in rapid succession.

**Automatic Response**:
- Circuit breaker trips from CLOSED to OPEN after N consecutive failures (default: 5).
- All subsequent packets are routed to the Dead Letter Queue.
- After recovery_timeout (default: 30s), breaker enters HALF_OPEN and probes with limited packets.
- If probes pass, breaker returns to CLOSED.

**Manual Override**:
```bash
# Force-reset the breaker
python -c "
from src.circuit_breaker import TelemetryCircuitBreaker
cb = TelemetryCircuitBreaker()
cb.reset()
print('Breaker state:', cb.state)
"
```

**DLQ Reprocessing** (after sensor calibration fix):
```bash
python -c "
from src.circuit_breaker import TelemetryCircuitBreaker
cb = TelemetryCircuitBreaker()
result = cb.reprocess_dlq(limit=100)
print(result)
"
```

---

### 3. Process Crash During Drain

**Symptom**: Process killed while drain batch is in DRAINING state.

**Automatic Response**:
- On next startup, call `recover_incomplete_batches()`.
- All DRAINING packets are rolled back to PENDING.
- Drain batch record is marked RECOVERED.
- No duplicates are sent because SYNCED is only set after cloud ACK.

**Startup Recovery Code**:
```python
buf = TracksideEdgeBuffer()
recovered = buf.recover_incomplete_batches()
print(f"Recovered {recovered} packets from incomplete batches")
buf.start_background_drain()
```

---

### 4. GDPR Audit Request

**Symptom**: Regulator or FIA requests proof of data handling for EU circuits.

**Response**:
```bash
python -c "
from src.audit_log import ComplianceAuditLog
log = ComplianceAuditLog()
print('Chain intact:', log.verify_chain())
print('Summary:', log.summary())
# Query specific jurisdiction
eu_entries = log.query_by_jurisdiction('EU', limit=50)
for e in eu_entries:
    print(e['timestamp'], e['action'], e['circuit'])
"
```

The audit log is:
- **Append-only**: No UPDATE or DELETE operations.
- **Hash-chained**: Each entry's SHA-256 hash includes the previous entry's hash.
- **Verifiable**: `verify_chain()` detects any tampering in O(n).

---

### 5. Schema Drift (Firmware Update)

**Symptom**: New sensor fields appear, or value ranges shift after a car firmware update.

**Response**:
1. Update `SchemaValidator.DEFAULT_RANGES` with new bounds.
2. Run DLQ reprocessing to recover any falsely quarantined packets.
3. The circuit breaker will auto-heal within one recovery_timeout cycle.

```python
from src.circuit_breaker import SchemaValidator
v = SchemaValidator(value_ranges={
    "new_sensor": (0.0, 500.0),  # Add new range
    "engine_temp": (-40.0, 1100.0),  # Widen existing range
})
```

---

### 6. Triple-Header Weekend (Sustained Load)

**Symptom**: 3 consecutive race weekends with no maintenance window.

**Mitigation**:
- Edge buffer auto-manages SQLite WAL checkpoints.
- DLQ depth monitored by Health Monitor (alerts at configurable threshold).
- Stress test validates 15-session sustained throughput:

```bash
python tools/telemetry_stress_test.py --showcase
```

---

## Monitoring Commands

```bash
# Real-time pit wall dashboard
python tools/health_monitor.py --interval 2

# Run full stress test
python tools/telemetry_stress_test.py --packets 5000 --chaos

# Verify audit chain integrity
python -c "from src.audit_log import ComplianceAuditLog; print(ComplianceAuditLog().verify_chain())"

# Check drain batch history
python -c "
from src.local_persistence import TracksideEdgeBuffer
buf = TracksideEdgeBuffer()
for b in buf.drain_history:
    print(b)
"
```

---

## Architecture Diagram

```
Car RF Downlink
      |
      v
[Request-ID Assigned] -- correlation tracing begins
      |
      v
[Circuit Breaker] -- SchemaValidator + three-state FSM
      |          \
      | (valid)   \--> [Dead Letter Queue] -- SQLite-backed quarantine
      v                       |
[Edge Buffer] -- SQLite WAL   |--> [DLQ Reprocessor] -- retry with updated ranges
      |
      v
[Geo-Fence] -- jurisdiction-aware PII scrub + audit logging
      |          \
      | (sync)    \--> [Compliance Audit Log] -- immutable hash chain
      v
[Cloud Sink] -- batch-ID exactly-once delivery
```
