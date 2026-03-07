# Pit Wall Integration Guide

**System:** Resilient RAP Framework — Cadillac F1 Telemetry Pipeline  
**Version:** 2.0 — 2026 Season  
**Audience:** Pit Wall Engineers, Data Acquisition Engineers, Crew Chief Support Staff

---

## Table of Contents

1. [Overview](#1-overview)
2. [Real-Time Alert Dashboard Schema](#2-real-time-alert-dashboard-schema)
3. [API Surface for Engineering Crew](#3-api-surface-for-engineering-crew)
4. [Response Time SLOs During Live Race](#4-response-time-slos-during-live-race)
5. [Crew Chief Decision Support](#5-crew-chief-decision-support)
6. [Example Queries and Alert Thresholds](#6-example-queries-and-alert-thresholds)
7. [Connectivity Loss Procedures](#7-connectivity-loss-procedures)
8. [Post-Race Forensics API](#8-post-race-forensics-api)

---

## 1. Overview

The pit wall integration layer sits between the Resilient RAP telemetry spine and the engineering crew's decision-support tools. It provides:

- **Sub-250 ms** safety-critical alerts to the crew chief workstation
- **Structured JSON events** consumed by strategy software and dashboards
- **Local-first guarantees** — the pit wall system continues operating even when the circuit network is degraded
- **Audit-ready provenance** for FIA steward inquiries

### Integration Architecture

```
Car RF Downlink (50 Hz)
        │
        ▼
Circuit Breaker ──→ DLQ (quarantine)
        │
        ▼
  Edge Buffer (local SQLite WAL)
        │
        ├──→ Kafka topic: telemetry-validated  ──→ Strategy Dashboard
        │
        ├──→ Kafka topic: telemetry-alerts     ──→ Crew Chief Workstation
        │
        └──→ Kafka topic: telemetry-dlq        ──→ Data Acq Engineer
```

### Key Properties

| Property | Guarantee |
|----------|-----------|
| Data durability | Zero packet loss — every packet written to SQLite before forwarding |
| Alert latency | < 250 ms for safety-critical sensors |
| Offline operation | Full local replay when circuit network is down |
| Audit trail | SHA-256 hash chain preserved for FIA inquiries |

---

## 2. Real-Time Alert Dashboard Schema

All alerts are published to Kafka topic `telemetry-alerts` as JSON objects.

### Alert Object

```json
{
  "alert_id": "ale_7f3d9b",
  "timestamp": "2026-05-25T14:32:17.843Z",
  "severity": "critical",
  "sensor": "engine_temp",
  "display_name": "Engine Coolant Temp",
  "value": 127.4,
  "unit": "°C",
  "threshold_breached": 125.0,
  "threshold_type": "critical",
  "nominal_range": [85.0, 120.0],
  "global_range": [-40.0, 1000.0],
  "track": "monaco",
  "track_range": [85.0, 118.0],
  "circuit_breaker_state": "CLOSED",
  "request_id": "req_abc123",
  "packet_id": "pkt_def456",
  "audit_hash": "sha256:ab3f...",
  "recovery_strategy": "dlq_reprocess",
  "safety_critical": true,
  "suggested_action": "Monitor closely. If > 130°C, consider lap delta reduction."
}
```

### Severity Levels

| Severity | Criteria | Destination | Response Time SLO |
|----------|---------|-------------|-------------------|
| `info` | Value within nominal range, informational | Dashboard only | < 1 s |
| `warning` | Value between nominal and warning threshold | Dashboard + engineer terminal | < 1 s |
| `critical` | Value exceeds critical threshold | Dashboard + crew chief console + audio alert | < 250 ms |
| `system_fault` | Circuit breaker trips to OPEN | All channels + escalation pager | < 250 ms |

### DLQ Event

```json
{
  "event_type": "dlq_ingestion",
  "dlq_record_id": "dlq_abc123",
  "timestamp": "2026-05-25T14:32:18.001Z",
  "sensor": "rpm",
  "failure_reason": "out_of_range|sensor=rpm|value=22000.0|expected=[0.0,20000.0]",
  "raw_value": 22000.0,
  "packet_id": "pkt_xyz789",
  "recoverable": true,
  "recovery_strategy": "dlq_reprocess"
}
```

---

## 3. API Surface for Engineering Crew

### Python API

The engineering crew can query the live pipeline from any Python environment connected to the local SQLite database:

```python
from src.circuit_breaker import TelemetryCircuitBreaker, DeadLetterQueue
from src.sensor_profiles import get_sensor_profile, get_track_ranges, PIT_WALL_ALERT_THRESHOLDS
from src.slo import SLOTracker

# ── Live System Status ──────────────────────────────────────────────────────

cb = TelemetryCircuitBreaker()
print("Breaker state:", cb.state)          # CLOSED | OPEN | HALF_OPEN
print("DLQ depth:", cb.dlq.pending_count())
print("Acceptance rate:", cb.metrics.acceptance_rate())

# ── Sensor Profile Lookup ────────────────────────────────────────────────────

profile = get_sensor_profile("engine_temp")
print("Nominal range:", profile.nominal_range())
print("Track range (Monaco):", get_track_ranges("engine_temp", "monaco"))
print("Alert thresholds:", PIT_WALL_ALERT_THRESHOLDS["engine_temp"])

# ── DLQ Inspection ──────────────────────────────────────────────────────────

dlq = DeadLetterQueue("data/telemetry.db")
pending = dlq.get_pending(limit=50)
for record in pending:
    print(f"  {record.sensor}: {record.reason}")

# ── SLO Check ───────────────────────────────────────────────────────────────

tracker = SLOTracker()
results = tracker.evaluate(
    latency_p95_ms=45.0,
    acceptance_rate=0.88,
    dlq_depth=350,
    audit_intact=True,
    detection_rate=0.95,
    breaker_trips=0,
    num_sessions=1,
)
tracker.print_report(results)
```

### CLI Quick-Reference

```bash
# System health snapshot
python -c "
from src.circuit_breaker import TelemetryCircuitBreaker
cb = TelemetryCircuitBreaker()
print('State:', cb.state)
print('DLQ pending:', cb.dlq.pending_count())
"

# Sensor profile lookup
python -c "
from src.sensor_profiles import get_sensor_profile
p = get_sensor_profile('engine_temp')
print('Nominal range:', p.nominal_range())
print('Safety critical:', p.safety_critical)
"

# DLQ status by reason
python -c "
import sqlite3
conn = sqlite3.connect('data/telemetry.db')
rows = conn.execute('''
    SELECT reason, count(*) AS cnt
    FROM dead_letter_queue WHERE status=\"pending\"
    GROUP BY reason ORDER BY cnt DESC
''').fetchall()
for r in rows: print(r)
"
```

---

## 4. Response Time SLOs During Live Race

These SLOs apply from Formation Lap through Chequered Flag:

| Alert Type | SLO | Measurement Point |
|-----------|-----|------------------|
| Safety-critical sensor alert | **< 250 ms** | Car RF → crew chief workstation |
| Non-critical sensor alert | **< 1,000 ms** | Car RF → engineer dashboard |
| DLQ depth check interval | **≤ 30 s** | Health monitor poll |
| Circuit breaker state change | **< 100 ms** | State transition → alert fire |
| Post-race forensics report | **< 5 min** | Chequered flag → report ready |
| Steward inquiry response | **< 15 min** | Request → audit package ready |

### SLO Monitoring

The health monitor (`tools/health_monitor.py`) tracks all SLOs in real time and flashes the dashboard when a threshold is approached:

```
┌─────────────────────────────────────────────────────────────┐
│  CADILLAC TELEMETRY HEALTH — LIVE                           │
├──────────────────┬──────────────────────┬───────────────────┤
│  Acceptance Rate │  88.2 %              │  ✅ PASS          │
│  P95 Latency     │  42 ms               │  ✅ PASS          │
│  DLQ Depth       │  287                 │  ✅ PASS          │
│  Breaker State   │  CLOSED              │  ✅ HEALTHY        │
│  Alert SLO       │  118 ms              │  ✅ WITHIN SLO    │
│  Audit Chain     │  Intact              │  ✅ VERIFIED       │
└──────────────────┴──────────────────────┴───────────────────┘
```

---

## 5. Crew Chief Decision Support

### Engine Temperature — Decision Tree

```
engine_temp reading received
        │
        ├── < 115°C ──────────────────────────────→ Normal, no action
        │
        ├── 115–125°C ─────────────────────────────→ WARNING
        │                                             • Log in strategy tool
        │                                             • Check cooling duct settings
        │                                             • Consider lap delta +0.1 s/sector
        │
        └── > 125°C ──────────────────────────────→ CRITICAL
                                                      • Audio alert to crew chief
                                                      • Consider engine mode reduction
                                                      • If > 130°C: advise driver
                                                      • If > 140°C: safety stop protocol
```

### Tyre Pressure — Decision Tree

```
tyre_pressure reading received
        │
        ├── > 22.5 psi ─────────────────────────────→ Normal
        │
        ├── 21.0–22.5 psi ──────────────────────────→ WARNING
        │                                              • Monitor tyre degradation
        │                                              • Consider pit window adjustment
        │
        └── < 21.0 psi ───────────────────────────→ CRITICAL
                                                      • FIA minimum breach risk
                                                      • Immediate pit call under
                                                        safety car if race situation allows
                                                      • Inform race director
```

### DLQ Depth — Crew Chief Guide

| DLQ Depth | Interpretation | Crew Chief Action |
|-----------|---------------|------------------|
| 0–500 | Normal — minor sensor noise | None |
| 500–2,500 | Elevated — possible sensor issue | Notify telemetry engineer |
| 2,500–5,000 | High — firmware issue suspected | Telemetry engineer investigates |
| > 5,000 | Critical — systemic sensor failure | Escalate to Data Acquisition Lead |

---

## 6. Example Queries and Alert Thresholds

### Alert Thresholds (2026 Cadillac Specification)

```python
# From src/sensor_profiles.py
PIT_WALL_ALERT_THRESHOLDS = {
    "engine_temp": {
        "warning":  115.0,   # °C
        "critical": 125.0,   # °C
    },
    "tyre_pressure": {
        "warning":  22.5,    # psi (lower threshold)
        "critical": 21.0,    # psi (FIA minimum)
    },
    "brake_temp": {
        "warning":  850.0,   # °C
        "critical": 1000.0,  # °C
    },
    "rpm": {
        "warning":  15000.0,
        "critical": 15500.0,
    },
    "heart_rate": {
        "warning":  185.0,   # bpm
        "critical": 210.0,   # bpm (FIA medical trigger)
    },
}
```

### SQLite Queries for Post-Session Review

```sql
-- Top DLQ failure reasons this session
SELECT reason, count(*) AS cnt
FROM dead_letter_queue
WHERE status = 'pending'
GROUP BY reason
ORDER BY cnt DESC;

-- Schema drift packets (recoverable)
SELECT packet_id, sensor, raw_value, created_at
FROM dead_letter_queue
WHERE reason LIKE 'schema_drift%'
  AND status = 'pending'
ORDER BY created_at DESC
LIMIT 50;

-- Safety-critical sensor failures
SELECT sensor, reason, raw_value, created_at
FROM dead_letter_queue
WHERE sensor IN ('engine_temp', 'tyre_pressure', 'brake', 'rpm')
  AND status = 'pending'
ORDER BY created_at DESC;

-- Audit chain verification
SELECT id, input_hash, output_hash, previous_hash, timestamp
FROM audit_log
ORDER BY id DESC
LIMIT 10;
```

### Real-Time Monitoring Loop

```python
import time
from src.circuit_breaker import TelemetryCircuitBreaker
from src.sensor_profiles import PIT_WALL_ALERT_THRESHOLDS

cb = TelemetryCircuitBreaker()

while True:
    metrics = cb.metrics
    dlq_depth = cb.dlq.pending_count()

    if cb.state.value != "CLOSED":
        print(f"⚠️  CIRCUIT BREAKER {cb.state.value} — investigate immediately")

    if dlq_depth > 2500:
        print(f"⚠️  DLQ DEPTH {dlq_depth} — elevated, check sensors")

    time.sleep(0.5)  # 500 ms refresh matches health monitor
```

---

## 7. Connectivity Loss Procedures

### Scenario: RF Link Degraded During Live Session

The trackside edge buffer (`src/local_persistence.py`) automatically handles connectivity loss:

1. **Detection:** Background drain thread fails to reach cloud endpoint
2. **Response:** All packets continue writing to local SQLite WAL (zero packet loss)
3. **Recovery:** When connectivity restores, background drain resumes automatically

```
Normal operation:         Car → Circuit Breaker → Edge Buffer → Cloud + Kafka
During connectivity loss: Car → Circuit Breaker → Edge Buffer (local only)
After recovery:           Edge Buffer drains backlog → Cloud + Kafka
```

**No manual intervention required** for connectivity durations < 30 minutes.

For extended outages (> 30 min), run:

```bash
# Check pending backlog
python -c "
from src.local_persistence import TracksideEdgeBuffer
buf = TracksideEdgeBuffer()
print('Pending packets:', buf.pending_count())
"

# Manually trigger drain
python -c "
from src.local_persistence import TracksideEdgeBuffer
buf = TracksideEdgeBuffer()
buf.drain_to_cloud(batch_size=1000)
"
```

### Scenario: Circuit WiFi Outage (Pit Wall → Factory)

The pit wall systems operate entirely on local infrastructure during outages:

- All telemetry continues locally at full rate
- DLQ, audit log, and edge buffer all write to local storage
- Strategy and data acquisition tools continue working from local database
- Factory link is advisory only; race decisions never depend on it

---

## 8. Post-Race Forensics API

### Quick Post-Race Package

```bash
# Generate forensics package within 5 minutes of chequered flag
python -c "
from src.circuit_breaker import DeadLetterQueue
from src.audit_log import AuditLog
import json, datetime

# 1. Export DLQ summary
dlq = DeadLetterQueue('data/telemetry.db')
summary = dlq.export_summary()

# 2. Verify audit chain
al = AuditLog()
chain_ok = al.verify_chain()

# 3. Generate report
report = {
    'timestamp': datetime.datetime.utcnow().isoformat(),
    'audit_chain_intact': chain_ok,
    'dlq_summary': summary,
}
with open('data/reports/post_race_forensics.json', 'w') as f:
    json.dump(report, f, indent=2)
print('Forensics package ready: data/reports/post_race_forensics.json')
"
```

### FIA Steward Inquiry Package

If stewards request data for a specific incident:

```python
from src.audit_log import AuditLog

al = AuditLog()

# Retrieve all audit records for a time window
records = al.query_range(
    start="2026-05-25T14:30:00",
    end="2026-05-25T14:35:00",
    sensor="engine_temp"
)

# Export as chain-verified JSON for stewards
al.export_steward_package(records, output_path="data/steward_inquiry_lap_32.json")
```

The steward package includes:
- All sensor readings for the requested time window
- SHA-256 hash chain verification proof
- DLQ records for rejected packets in the same window
- Geo-fence jurisdiction confirmation (relevant for EU circuits)

See [COMPLIANCE_VERIFICATION.md](COMPLIANCE_VERIFICATION.md) for the full FIA compliance workflow.
