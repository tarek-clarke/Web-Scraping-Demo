# Race Weekend Runbook

**System:** Resilient RAP Framework — Telemetry Platform Telemetry Pipeline  
**Version:** 2.0  
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
| 9 | SLO baseline run | `python tools/telemetry_stress_test.py --sessions 1 --packets 1000` | All SLOs PASS |
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
python tools/telemetry_stress_test.py --report-only

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
