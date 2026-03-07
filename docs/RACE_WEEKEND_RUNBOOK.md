# Race Weekend Runbook

**System:** Resilient RAP Framework — Cadillac F1 Telemetry Pipeline  
**Version:** 2.1 — 2026 Season  
**Maintained by:** Tarek Clarke

---

## Table of Contents

1. [Pre-Race Checklist](#1-pre-race-checklist)
2. [Race-Day Startup Procedure](#2-race-day-startup-procedure)
3. [Live Monitoring Procedure](#3-live-monitoring-procedure)
4. [Alert Response — DLQ Depth](#4-alert-response--dlq-depth)
5. [Alert Response — Circuit Breaker Trip](#5-alert-response--circuit-breaker-trip)
6. [Alert Response — Latency Budget Exceeded](#6-alert-response--latency-budget-exceeded)
7. [Alert Response — SLO Breach](#7-alert-response--slo-breach)
8. [Post-Race: Data Drain & Reconciliation](#8-post-race-data-drain--reconciliation)
9. [Escalation Contacts](#9-escalation-contacts)
10. [Glossary](#10-glossary)
11. [FP1 → Qualifying → Race Progression](#11-fp1--qualifying--race-progression)
12. [Known 2026 Cadillac Sensor Ranges](#12-known-2026-cadillac-sensor-ranges)
13. [Live Incident Response — Motorsport-Specific](#13-live-incident-response--motorsport-specific)
14. [Pit Wall Command Integration](#14-pit-wall-command-integration)
15. [Post-Race Forensics Workflow](#15-post-race-forensics-workflow)

---

## 1. Pre-Race Checklist

Complete **≥ 2 hours** before green flag.

| # | Check | Command / Method | Pass Criterion |
|---|-------|-----------------|----------------|
| 1 | All tests pass | `pytest tests/ -v --tb=short` | 0 failures |
| 2 | Lint clean | `flake8 src/ tools/ modules/` | 0 errors |
| 3 | SQLite WAL reachable | `python main.py --health-check` | `OK` |
| 4 | Edge buffer not full | Check `data/edge_buffer.db` size | < 200 MB |
| 5 | DLQ empty | `SELECT count(*) FROM dead_letter_queue WHERE status='pending'` | 0 |
| 6 | Audit chain intact | `python -c "from src.audit_log import AuditLog; print(AuditLog().verify_chain())"` | `True` |
| 7 | Geo-fence config loaded | `python -c "from src.geo_fence import GeoFence; GeoFence().validate_config()"` | No exception |
| 8 | Circuit breaker CLOSED | `python -c "from src.circuit_breaker import TelemetryCircuitBreaker; print(TelemetryCircuitBreaker().state)"` | `CLOSED` |
| 9 | SLO baseline run | `python tools/cadillac_stress_test.py --sessions 1 --packets 1000` | All SLOs PASS |
| 10 | Health monitor starts | `python tools/health_monitor.py` | Dashboard renders |

---

## 2. Race-Day Startup Procedure

```bash
# 1. Activate environment
source .venv/bin/activate          # or: conda activate rap-env

# 2. Confirm Python version
python --version                   # must be 3.10+

# 3. Start ingestion (background)
python main.py --mode live &
INGESTOR_PID=$!

# 4. Start health monitor (separate terminal)
python tools/health_monitor.py

# 5. Confirm both are running
ps aux | grep -E "main.py|health_monitor"
```

> **Note:** If running in Docker, replace the above with:  
> `docker compose up -d && docker compose logs -f`

---

## 3. Live Monitoring Procedure

The health monitor (`tools/health_monitor.py`) refreshes every **500 ms** and shows:

| Panel | What to Watch |
|-------|--------------|
| Acceptance Rate | Must stay **> 80 %**; alarm at < 75 % |
| DLQ Depth | Must stay **< 5,000**; alarm at > 2,500 |
| P95 Latency | Must stay **< 100 ms**; alarm at > 80 ms |
| Circuit Breaker | CLOSED = healthy; OPEN = critical |
| Last Audit Hash | Should change every ~30 s |

**Normal operating range during a live session:**

```
Acceptance rate : 83–95 %
P95 latency     : 40–70 ms
DLQ depth       : 0–500
Breaker trips   : 0
```

---

## 4. Alert Response — DLQ Depth

**Trigger:** DLQ depth > 2,500

### Step 1: Identify the dominant failure reason

```sql
-- Run against the local SQLite database
SELECT reason, count(*) AS cnt
FROM dead_letter_queue
WHERE status = 'pending'
GROUP BY reason
ORDER BY cnt DESC;
```

### Step 2: Triage by reason

| Reason | Action |
|--------|--------|
| `schema_drift` | Run DLQ reprocessor — packets are recoverable |
| `null_value` | Investigate sensor / firmware update on affected channels |
| `bit_flip_high` | Check CAN-bus shielding; flag lap for manual review |
| `bit_flip_low` | Low priority; let accumulate until post-session |
| `string_in_numeric` | Firmware parse regression — alert telemetry engineer |
| `duplicate_timestamp` | Clock sync issue; alert data acquisition team |
| `sensor_dropout` | Hardware fault; notify crew chief immediately |

### Step 3: Trigger reprocessing for schema_drift

```python
from src.circuit_breaker import TelemetryCircuitBreaker, DeadLetterQueue

dlq = DeadLetterQueue("data/telemetry.db")
recovered = dlq.reprocess_schema_drift()      # uses normalisation pass
print(f"Recovered: {recovered}")
```

### Step 4: If depth still growing after reprocessing

1. Enable **backpressure mode** — ingestion rate reduced by 50 %:
   ```python
   from src.circuit_breaker import TelemetryCircuitBreaker
   cb = TelemetryCircuitBreaker()
   cb.enable_backpressure()
   ```
2. Alert Escalation Tier 1 (see §9)
3. Log incident in `data/provenance_log.jsonl`

---

## 5. Alert Response — Circuit Breaker Trip

**Trigger:** State transitions to `OPEN`

### Immediate (< 1 min)

1. Note the timestamp and failing sensor name from the audit log:
   ```bash
   tail -50 data/provenance_log.jsonl | python -m json.tool | grep -A5 "circuit_breaker"
   ```
2. Identify if the failure is localised (one sensor) or systemic (multiple sensors).
3. **Do not** restart the ingestor immediately — let the half-open probe run.

### After HALF_OPEN probe (automatic, 30 s)

| Probe Result | Next State | Your Action |
|---|---|---|
| Probe passes | → CLOSED | Monitor closely for 2 minutes |
| Probe fails | → OPEN again | Begin manual investigation |

### Manual recovery (if breaker stays OPEN)

```python
from src.circuit_breaker import TelemetryCircuitBreaker

cb = TelemetryCircuitBreaker()
# Force reset ONLY after root cause is confirmed
cb.manual_reset(reason="sensor_X confirmed healthy by engineer")
```

> **CRITICAL:** Never manually reset without confirming root cause. A premature reset during live running risks corrupt data entering the pipeline silently.

---

## 6. Alert Response — Latency Budget Exceeded

**Trigger:** P95 latency > 80 ms (warning) or > 100 ms (breach)

### Diagnostics

```bash
# Tail the real-time latency CSV
tail -100 data/reports/resilience_timing_report.csv \
  | awk -F',' 'NR>1 {sum+=$3; n++} END {print "mean ms:", sum/n}'
```

### Common causes and fixes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Latency spike on all sensors | DB write contention | Increase WAL checkpoint interval |
| Latency spike on one sensor | Schema validation loop | Check DLQ for schema_drift on that sensor |
| Sustained latency > 150 ms | GIL contention / CPU saturation | Reduce chaos injection rate in stress test OR scale workers |
| Intermittent latency spikes | GC pressure | Profile with `cProfile`; increase GC thresholds |

---

## 7. Alert Response — SLO Breach

Run the SLO tracker at any time to get a structured report:

```python
from src.slo import SLOTracker

tracker = SLOTracker()
results = tracker.evaluate(
    latency_p95_ms=XX,
    acceptance_rate=XX,
    dlq_depth=XX,
    audit_intact=True,
    detection_rate=XX,
    breaker_trips=XX,
    num_sessions=XX,
)
tracker.print_report(results)
```

For each violated SLO, consult the relevant section in this runbook:

| Violated SLO | Runbook Section |
|---|---|
| LATENCY_P95 | §6 |
| ACCEPTANCE_RATE | §4 (increase DLQ recovery rate) |
| DLQ_DEPTH | §4 |
| AUDIT_INTEGRITY | Contact Data Integrity Lead immediately |
| DETECTION_RATE | Review chaos engine thresholds; may indicate a schema regression |
| BREAKER_TRIPS_PER_SESSION | §5 |

---

## 8. Post-Race: Data Drain & Reconciliation

Execute **within 30 minutes** of chequered flag.

```bash
# 1. Stop live ingestor gracefully
kill -SIGTERM $INGESTOR_PID

# 2. Drain edge buffer to persistent store
python main.py --drain-edge-buffer

# 3. Run DLQ reprocessor on full DLQ
python -c "
from src.circuit_breaker import DeadLetterQueue
dlq = DeadLetterQueue('data/telemetry.db')
n = dlq.reprocess_all()
print(f'DLQ reprocessed: {n} packets recovered')
"

# 4. Verify audit chain integrity
python -c "
from src.audit_log import AuditLog
al = AuditLog()
ok = al.verify_chain()
print('Audit chain intact:', ok)
"

# 5. Generate final race report
python tools/cadillac_stress_test.py --report-only

# 6. Archive reports
cp -r data/reports/ archive/race_$(date +%Y%m%d)/

# 7. Commit data artifacts (NOT model weights, NOT raw telemetry)
git add data/reports/ data/provenance_log.jsonl
git commit -m "chore: post-race data reconciliation $(date +%F)"
```

### Reconciliation checklist

| # | Task | Pass Criterion |
|---|------|----------------|
| 1 | Edge buffer drained | Buffer size = 0 |
| 2 | DLQ reprocessed | Pending count reduced |
| 3 | Audit chain verified | `True` |
| 4 | SLOs reported | Report generated |
| 5 | Reports archived | Files present in `archive/` |
| 6 | Provenance log complete | No gaps in sequence |

---

## 9. Escalation Contacts

| Tier | Role | When to Escalate |
|------|------|-----------------|
| **T1** | Telemetry Engineer | DLQ depth > 5,000 or any SLO breach during live running |
| **T2** | Data Acquisition Lead | Circuit breaker stays OPEN > 5 min |
| **T3** | Head of Vehicle Performance | Audit chain corrupt; sensor_dropout on safety-critical channels |

---

## 10. Glossary

| Term | Definition |
|------|-----------|
| **DLQ** | Dead Letter Queue — quarantine for packets that failed validation |
| **Circuit Breaker** | Fault-isolation state machine (CLOSED → OPEN → HALF_OPEN) |
| **Schema Drift** | Sensor name change between firmware versions; values remain valid |
| **Edge Buffer** | Local SQLite store that persists packets during connectivity outages |
| **SLO** | Service Level Objective — a numerical contract for pipeline behaviour |
| **Audit Chain** | Hash-linked provenance log; tampering breaks the chain |
| **Backpressure** | Deliberate ingestion slowdown to prevent DLQ overflow |
| **WAL** | Write-Ahead Log — SQLite mode that improves concurrent write throughput |
| **FP1/FP2/FP3** | Free Practice sessions 1, 2, and 3 |
| **Q1/Q2/Q3** | Qualifying segments 1, 2, and 3 |
| **Pit Wall** | Engineering station at pit lane monitoring live telemetry |
| **Sensor Profile** | 2026 Cadillac specification for a single telemetry sensor |
| **Bit-Flip** | Single-bit hardware corruption producing an impossible sensor value |
| **Firmware Alias** | Historical field name from an older ECU firmware version |

---

## 11. FP1 → Qualifying → Race Progression

### FP1 — Initial Validation

FP1 is used to validate pipeline health under live conditions before race-critical sessions:

```
Pre-FP1 (T−3h):  Full deployment checklist (see CADILLAC_DEPLOYMENT_CHECKLIST.md)
FP1 running:      Monitor acceptance rate; expect 85–95% with healthy car
Post-FP1:         DLQ analysis; identify sensor fault patterns for Q/Race prep
```

**FP1 Success Criteria:**

| Metric | Target |
|--------|--------|
| Acceptance rate | > 80% |
| P95 latency | < 100 ms |
| Circuit breaker trips | 0 |
| DLQ depth (final) | < 5,000 |
| Audit chain | Intact |

**Post-FP1 DLQ Review:**

```sql
-- Identify top failure reasons from FP1
SELECT reason, count(*) AS cnt, sensor
FROM dead_letter_queue
WHERE status = 'pending'
  AND created_at > datetime('now', '-3 hours')
GROUP BY reason, sensor
ORDER BY cnt DESC
LIMIT 20;
```

### FP2 / FP3 — Progressive Refinement

Between sessions:

1. Reprocess schema-drift DLQ entries from previous session
2. Verify circuit breaker auto-recovered if it tripped
3. Update sensor alert thresholds if track conditions changed (e.g., wet → dry)
4. Check firmware version — mid-session updates require alias table reload

```bash
# Reprocess schema-drift packets from FP1 before FP2
PYTHONPATH="." python -c "
from src.circuit_breaker import TelemetryCircuitBreaker
cb = TelemetryCircuitBreaker()
result = cb.reprocess_dlq(limit=5000)
print('Recovered:', result)
"
```

### Qualifying — Heightened Monitoring

Q sessions are typically shorter and higher stakes than practice:

- Reduce health monitor refresh to **250 ms** (default is 500 ms)
- Pre-configure audio alerts for engine_temp, tyre_pressure
- Keep DLQ reprocessing running in background (auto-recovery)
- Do NOT manually reset breaker during Q2/Q3 unless root cause confirmed

### Race — Full Production Mode

```
Formation lap: Monitor-only — no config changes
Race start:    Full monitoring, all safety-critical alerts active
SC period:     Check for sensor anomalies during slow lap
VSC period:    DLQ reprocess opportunity (low-risk, slow lap)
Pit stops:     Monitor tyre_pressure + brake_temp closely
Final lap:     Prepare post-race archive commands
Flag:          Execute post-race archival within 5 minutes
```

---

## 12. Known 2026 Cadillac Sensor Ranges

These are the validated operating ranges for the Cadillac 2026 car across typical race conditions.

### Global Ranges (Circuit Breaker Limits)

| Sensor | Min | Max | Unit | Fault Pattern |
|--------|-----|-----|------|--------------|
| speed | 0.0 | 380.0 | km/h | bit_flip |
| rpm | 0.0 | 20,000 | RPM | bit_flip, schema_drift |
| throttle | 0.0 | 100.0 | % | stuck_value |
| brake | 0.0 | 100.0 | % | sensor_dropout |
| engine_temp | −40.0 | 1,000.0 | °C | bit_flip, schema_drift |
| tyre_pressure | 15.0 | 35.0 | psi | sensor_dropout |
| brake_temp | 50.0 | 1,200.0 | °C | bit_flip, noise_burst |
| aero_load | −500.0 | 3,000.0 | N | bit_flip |
| g_force_lateral | −8.0 | 8.0 | G | bit_flip |
| g_force_longitudinal | −8.0 | 8.0 | G | bit_flip |
| g_force_vertical | −5.0 | 5.0 | G | bit_flip |
| heart_rate | 30.0 | 250.0 | bpm | sensor_dropout |
| ecu_canbus | −1,000,000 | 1,000,000 | raw | can_bus |

### Track-Specific Ranges (Monaco vs. Monza)

| Sensor | Monaco | Monza | Notes |
|--------|--------|-------|-------|
| speed max | 295 km/h | 370 km/h | Monza = high-speed power circuit |
| engine_temp max | 118°C | 115°C | Monza = better cooling airflow |
| brake_temp typical | 200–750°C | 200–600°C | Monaco = more braking zones |
| tyre_pressure min | 22 psi | 21 psi | Monaco = higher lateral load |
| aero_load range | 800–2,500 N | 200–1,200 N | Monaco = max downforce |
| rpm typical | 4,000–14,000 | 10,000–15,500 | Monza = constant high RPM |

Full per-circuit ranges are defined in `src/sensor_profiles.py`:

```python
from src.sensor_profiles import get_track_ranges

# Monaco engine temperature limit
lo, hi = get_track_ranges("engine_temp", "monaco")
print(f"Monaco engine_temp: {lo}–{hi}°C")  # 85.0–118.0°C
```

---

## 13. Live Incident Response — Motorsport-Specific

### Incident: Multi-Sensor Bit-Flip Cascade

**Symptom:** 5+ sensors reporting impossible values simultaneously (e.g., after firmware update applied during red flag)

**Automated Response:**
1. Circuit breaker trips to OPEN after 5 consecutive failures
2. All packets routed to DLQ
3. HALF_OPEN probe triggers after 30 s recovery timeout

**Manual Response Procedure:**

```bash
# Step 1: Check which sensors are failing
PYTHONPATH="." python -c "
from src.circuit_breaker import DeadLetterQueue
dlq = DeadLetterQueue()
recent = dlq.recent(limit=100)
sensors = {}
for r in recent:
    sensors[r.sensor] = sensors.get(r.sensor, 0) + 1
for s, n in sorted(sensors.items(), key=lambda x: -x[1]):
    print(f'  {s}: {n} failures')
"

# Step 2: Check firmware version (if schema drift suspected)
# Verify with telemetry engineer whether ECU update was applied

# Step 3: If firmware update confirmed, load new alias table
PYTHONPATH="." python -c "
from src.sensor_profiles import FIRMWARE_COMPAT_MATRIX
# List all firmware versions and their aliases
for fw, aliases in FIRMWARE_COMPAT_MATRIX.items():
    print(f'{fw}: {list(aliases.keys())}')
"

# Step 4: Reprocess DLQ after firmware alias confirmed
PYTHONPATH="." python -c "
from src.circuit_breaker import TelemetryCircuitBreaker
cb = TelemetryCircuitBreaker()
result = cb.reprocess_dlq(limit=10000)
print('Recovered:', result)
"
```

### Incident: Trackside Connectivity Loss

**Symptom:** Cloud uplink severed; pit wall disconnected from factory data systems

**Automated Response:**
- Edge buffer continues writing locally at full rate
- Zero packet loss (SQLite WAL guarantees durability)
- Background drain pauses automatically

**Manual Response Procedure:**

```bash
# Confirm local buffer is absorbing packets
PYTHONPATH="." python -c "
from src.local_persistence import TracksideEdgeBuffer
buf = TracksideEdgeBuffer()
print('Pending for drain:', buf.pending_count())
print('Local buffer healthy — no data loss')
"

# When connectivity restored, trigger manual drain
PYTHONPATH="." python -c "
from src.local_persistence import TracksideEdgeBuffer
buf = TracksideEdgeBuffer()
n = buf.drain_to_persistent()
print(f'Drained: {n} packets')
"
```

### Incident: Schema Drift After Mid-Season ECU Update

**Symptom:** DLQ filling with `schema_drift` errors after FP1 of a mid-season round

**Root Cause:** ECU firmware updated between races; sensor field names changed

**Resolution:**

```bash
# Step 1: Identify the new firmware field names from DLQ
PYTHONPATH="." python -c "
from src.circuit_breaker import DeadLetterQueue
dlq = DeadLetterQueue()
for r in dlq.recent(limit=50):
    if 'schema_drift' in r.reason:
        print(f'  sensor={r.sensor} value={r.raw_value}')
"

# Step 2: Check if new field name is already in alias table
PYTHONPATH="." python -c "
from src.sensor_profiles import get_sensor_profile
# Try looking up the new field name
profile = get_sensor_profile('TwaterOut')  # replace with actual new name
print('Resolved to:', profile.name if profile else 'NOT FOUND')
"

# Step 3: If alias exists, reprocess DLQ
# If alias NOT found: add new firmware alias to FIRMWARE_COMPAT_MATRIX
# and restart the pipeline
```

---

## 14. Pit Wall Command Integration

See [PIT_WALL_INTEGRATION.md](PIT_WALL_INTEGRATION.md) for the full API reference.

### Quick Commands for Pit Wall Engineers

```bash
# Live system status (run any time)
PYTHONPATH="." python -c "
from src.circuit_breaker import TelemetryCircuitBreaker
cb = TelemetryCircuitBreaker()
m = cb.metrics
print('State:', cb.state.value)
print('DLQ depth:', cb.dlq.depth())
"

# Check specific sensor health
PYTHONPATH="." python -c "
from src.sensor_profiles import get_sensor_profile, get_track_ranges

sensor = 'engine_temp'
track = 'monaco'

profile = get_sensor_profile(sensor)
lo, hi = get_track_ranges(sensor, track)
print(f'{profile.display_name} at {track}: {lo}–{hi} {profile.unit}')
print('Safety critical:', profile.safety_critical)
"

# Force circuit breaker reset (use only with confirmed root cause)
PYTHONPATH="." python -c "
from src.circuit_breaker import TelemetryCircuitBreaker
cb = TelemetryCircuitBreaker()
cb.reset()
print('Breaker state after reset:', cb.state.value)
"
```

### Alert Threshold Quick Reference

| Sensor | Warning | Critical | Action |
|--------|---------|----------|--------|
| engine_temp | 115°C | 125°C | Monitor / Engine mode reduction |
| tyre_pressure | 22.5 psi | 21.0 psi | Consider pit call |
| brake_temp | 850°C | 1,000°C | Reduce brake bias |
| rpm | 15,000 | 15,500 | Auto engine mapping switch |
| heart_rate | 185 bpm | 210 bpm | FIA medical delegate |

---

## 15. Post-Race Forensics Workflow

Execute post-race forensics to support debrief, FIA compliance, and steward inquiries.

### Step 1: Immediate Post-Race (< 5 min)

```bash
# Generate forensics snapshot
PYTHONPATH="." python tools/verify_compliance.py \
  --all \
  --circuit CIRCUIT_NAME \
  --report \
  --output data/forensics_$(date +%Y%m%d_%H%M%S).json
```

### Step 2: DLQ Analysis (< 30 min)

```sql
-- Full DLQ breakdown for race debrief
SELECT
    sensor,
    reason,
    count(*) AS count,
    min(created_at) AS first_seen,
    max(created_at) AS last_seen
FROM dead_letter_queue
WHERE created_at > datetime('now', '-6 hours')
GROUP BY sensor, reason
ORDER BY count DESC;
```

### Step 3: Audit Chain Export for FIA

```bash
PYTHONPATH="." python tools/verify_compliance.py \
  --steward-package \
  --start RACE_START_TIME \
  --end RACE_END_TIME \
  --circuit CIRCUIT_NAME \
  --output data/fia_audit_package_$(date +%Y%m%d).json
```

### Step 4: Archive

```bash
RACE_DATE=$(date +%Y%m%d)
mkdir -p archive/race_${RACE_DATE}
cp -r data/reports/ archive/race_${RACE_DATE}/reports/
cp data/forensics_*.json archive/race_${RACE_DATE}/
cp data/fia_audit_package_*.json archive/race_${RACE_DATE}/
echo "Race ${RACE_DATE} archived successfully"
```

### Forensics Checklist

| # | Task | Pass Criterion |
|---|------|----------------|
| 1 | Audit chain verified post-race | `True` |
| 2 | Compliance report generated | File saved |
| 3 | DLQ analysis complete | Top reasons identified |
| 4 | Schema drift packets recovered | Reprocessed count > 0 |
| 5 | FIA audit package ready | Package file saved |
| 6 | Data archived | `archive/race_YYYYMMDD/` present |
| 7 | Budget cap report | Engineer-hours saved documented |
