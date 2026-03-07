# Cadillac 2026 Production Deployment Checklist

**System:** Resilient RAP Framework — Cadillac F1 Telemetry Pipeline  
**Version:** 2.0 — 2026 Season  
**Updated:** 2026-03-07  
**Authority:** Cadillac Motorsports Data Acquisition Team

---

## Purpose

This checklist ensures the telemetry pipeline is fully operational before each race weekend session. It covers Pre-FP1 validation, calibration verification, pit wall readiness, post-race archival, and triple-header operational patterns.

---

## Table of Contents

1. [Pre-FP1 Validation](#1-pre-fp1-validation)
2. [Sensor Calibration Verification](#2-sensor-calibration-verification)
3. [Pit Wall System Readiness](#3-pit-wall-system-readiness)
4. [Session Progression (FP1 → FP2 → FP3 → Q → Race)](#4-session-progression)
5. [Post-Race Data Archival](#5-post-race-data-archival)
6. [Steward Inquiry Readiness](#6-steward-inquiry-readiness)
7. [Triple-Header Operational Patterns](#7-triple-header-operational-patterns)
8. [Deployment Sign-Off](#8-deployment-sign-off)

---

## 1. Pre-FP1 Validation

Complete **≥ 3 hours** before FP1 green flag.

### 1.1 Environment Validation

| # | Check | Command | Pass Criterion |
|---|-------|---------|----------------|
| 1 | Python version ≥ 3.10 | `python --version` | `3.10.x` or higher |
| 2 | All tests pass | `PYTHONPATH="." pytest tests/ -v --timeout=120` | 0 failures |
| 3 | Lint clean | `flake8 src/ tests/ tools/ --max-line-length 120` | 0 errors |
| 4 | GPU detected (if available) | `python -c "import torch; print(torch.cuda.is_available())"` | `True` |
| 5 | ROCm/CUDA version | `python -c "import torch; print(torch.version.hip or torch.version.cuda)"` | Expected version |

### 1.2 Pipeline Validation

| # | Check | Command | Pass Criterion |
|---|-------|---------|----------------|
| 6 | Circuit breaker CLOSED | `python -c "from src.circuit_breaker import TelemetryCircuitBreaker; cb = TelemetryCircuitBreaker(); print(cb.state)"` | `CircuitState.CLOSED` |
| 7 | DLQ empty | `python -c "from src.circuit_breaker import DeadLetterQueue; dlq = DeadLetterQueue(); print('DLQ depth:', dlq.depth())"` | `0` |
| 8 | Audit chain intact | `python -c "from src.audit_log import ComplianceAuditLog; al = ComplianceAuditLog(); print(al.verify_chain())"` | `True` |
| 9 | Edge buffer clear | `python -c "from src.local_persistence import TracksideEdgeBuffer; buf = TracksideEdgeBuffer(); print('Pending:', buf.pending_count())"` | `0` |
| 10 | Geo-fence loaded | `python -c "from src.geo_fence import GeoFence; GeoFence().resolve_jurisdiction('CIRCUIT_NAME')"` | No exception |

### 1.3 Sensor Profile Validation

```bash
# Verify 2026 sensor catalogue
python -c "
from src.sensor_profiles import CADILLAC_2026_SENSORS, list_safety_critical_sensors
print('Sensor count:', len(CADILLAC_2026_SENSORS))
print('Safety critical:', list_safety_critical_sensors())
"

# Verify firmware compatibility matrix
python -c "
from src.sensor_profiles import FIRMWARE_COMPAT_MATRIX
for fw, aliases in FIRMWARE_COMPAT_MATRIX.items():
    print(f'{fw}: {len(aliases)} aliases')
"
```

Expected output:
```
Sensor count: 16
Safety critical: ['rpm', 'brake', 'engine_temp', 'tyre_pressure']
fw_2024_q4: 11 aliases
fw_2025_pre: 10 aliases
fw_2025_r1: 7 aliases
fw_2026_launch: 0 aliases
```

### 1.4 Compliance Pre-Check

```bash
# Run full compliance check for the race circuit
python tools/verify_compliance.py --all --circuit CIRCUIT_NAME
```

| # | Check | Pass Criterion |
|---|-------|----------------|
| 11 | GDPR checks pass | All GDPR checks `✅` |
| 12 | FIA audit trail | Hash chain intact |
| 13 | Data sovereignty | Jurisdiction identified |
| 14 | Overall compliance | `ALL PASSED` |

---

## 2. Sensor Calibration Verification

Complete **≥ 1 hour** before FP1.

### 2.1 Cadillac 2026 Expected Ranges

Verify calibration against these 2026 baseline specifications:

| Sensor | Expected Range | Unit | Calibration Check |
|--------|---------------|------|------------------|
| speed | 0 – 380 | km/h | Zero-speed check at rest |
| rpm | 0 – 15,500 | RPM | Idle = ~900 RPM |
| throttle | 0 – 100 | % | Pedal-to-floor = 100% |
| brake | 0 – 100 | % | No input = 0% |
| gear | 1 – 8 | gear | Neutral = 0 |
| engine_temp | 85 – 120 | °C | Cold engine = ~40°C warming to 85°C+ |
| tyre_pressure | 21 – 26 | psi | Pre-heat = 18–20 psi |
| brake_temp | 200 – 900 | °C | Cold = 50°C; post-brake-test = 200°C+ |
| g_force_lateral | −6 – 6 | G | Stationary = ~0.0 G |
| g_force_longitudinal | −6 – 5 | G | Stationary = ~0.0 G |
| aero_load | 200 – 2,500 | N | Stationary = ~100–200 N (car weight) |
| heart_rate | 60 – 200 | bpm | Pre-race = ~70–100 bpm |

### 2.2 Calibration Validation Script

```bash
PYTHONPATH="." python -c "
from src.sensor_profiles import CADILLAC_2026_SENSORS
from src.circuit_breaker import SchemaValidator, TelemetryPacket

# Test static readings against nominal ranges
test_values = {
    'speed': 0.0,
    'rpm': 900.0,
    'throttle': 0.0,
    'brake': 0.0,
    'engine_temp': 40.0,
    'tyre_pressure': 19.0,
}

v = SchemaValidator()
for sensor, value in test_values.items():
    pkt = TelemetryPacket(sensor=sensor, value=value)
    ok, reason = v.validate_packet(pkt)
    print(f'  {sensor}: {value} → {\"OK\" if ok else reason}')
"
```

### 2.3 Firmware Version Check

```bash
python -c "
from src.sensor_profiles import FIRMWARE_COMPAT_MATRIX
# Confirm 2026 launch firmware is active (no aliases required)
launch_fw = FIRMWARE_COMPAT_MATRIX.get('fw_2026_launch', {})
print('2026 launch firmware aliases (should be empty):', len(launch_fw))
assert len(launch_fw) == 0, 'ERROR: fw_2026_launch should have 0 aliases'
print('✅ Firmware fw_2026_launch confirmed')
"
```

---

## 3. Pit Wall System Readiness

Complete **≥ 30 minutes** before FP1.

### 3.1 Health Monitor

```bash
# Start health monitor (keep running in separate terminal)
PYTHONPATH="." python tools/health_monitor.py

# Expected: Dashboard renders, all panels green
```

| Panel | Healthy Value | Alert Threshold |
|-------|--------------|-----------------|
| Acceptance Rate | > 85% | < 75% |
| DLQ Depth | 0 | > 2,500 |
| P95 Latency | < 50 ms | > 80 ms |
| Circuit Breaker | CLOSED | OPEN |
| Audit Chain | Intact | Broken |

### 3.2 Alert Thresholds Configured

```bash
python -c "
from src.sensor_profiles import PIT_WALL_ALERT_THRESHOLDS, PIT_WALL_SLO_SECONDS
print('Alert thresholds configured:')
for sensor, thresholds in PIT_WALL_ALERT_THRESHOLDS.items():
    print(f'  {sensor}: warning={thresholds[\"warning\"]}, critical={thresholds[\"critical\"]}')
print()
print('SLOs:')
for name, slo in PIT_WALL_SLO_SECONDS.items():
    print(f'  {name}: {slo}s')
"
```

### 3.3 Pit Wall Integration Checks

| # | Check | Pass Criterion |
|---|-------|----------------|
| 15 | Health monitor renders | Dashboard visible, all panels |
| 16 | Alert thresholds loaded | 5 sensors configured |
| 17 | Safety-critical SLO | < 250 ms confirmed |
| 18 | Kafka integration (if enabled) | Topics `telemetry-validated` + `telemetry-dlq` reachable |
| 19 | Strategy software connected | Strategy tool sees live feed |

---

## 4. Session Progression

### FP1 → FP2 → FP3 Flow

```
FP1                     FP2                     FP3
│                       │                       │
├── Pre-session check   ├── Review FP1 DLQ      ├── Review FP2 DLQ
├── Start live ingest   ├── Reprocess if needed  ├── Final calibration
├── Monitor health      ├── Adjust thresholds    ├── Confirm race config
├── Post-session drain  ├── Post-session drain   └── Post-session drain
└── DLQ analysis        └── DLQ analysis
```

### Qualifying Day (Q1 → Q2 → Q3)

| Phase | Action |
|-------|--------|
| Pre-Q1 | Full pre-session check (same as Pre-FP1) |
| Q1 → Q2 break | Quick DLQ check; no reprocessing unless critical |
| Q2 → Q3 break | Confirm breaker CLOSED; DLQ depth check |
| Post-Q3 | Full post-session drain; archive qualifying data |

### Race Day

| Phase | Action | Time |
|-------|--------|------|
| Pre-race (formation) | Pre-race checklist complete | T−3h |
| Formation lap | Monitor-only; no changes | T−0:05 |
| Race start | Full monitoring, all alerts active | T+0 |
| Safety car | DLQ check; monitor for sensor anomalies | As needed |
| Pit windows | Monitor tyre pressure + brake temp closely | Each stop |
| Final lap | Prepare post-race archive script | T−1 lap |
| Chequered flag | Start post-race drain immediately | T+0 |
| T+5 min | Generate forensics report | T+5 |
| T+30 min | Full post-race archival complete | T+30 |

---

## 5. Post-Race Data Archival

Execute **within 30 minutes** of chequered flag.

```bash
# 1. Stop live ingestor gracefully
kill -SIGTERM $INGESTOR_PID

# 2. Drain edge buffer
PYTHONPATH="." python -c "
from src.local_persistence import TracksideEdgeBuffer
buf = TracksideEdgeBuffer()
n = buf.drain_to_persistent()
print(f'Drained: {n} packets')
"

# 3. Reprocess DLQ (schema drift packets)
PYTHONPATH="." python -c "
from src.circuit_breaker import TelemetryCircuitBreaker
cb = TelemetryCircuitBreaker()
result = cb.reprocess_dlq(limit=10000)
print('DLQ reprocessed:', result)
"

# 4. Verify audit chain
PYTHONPATH="." python -c "
from src.audit_log import ComplianceAuditLog
al = ComplianceAuditLog()
ok = al.verify_chain()
print('Audit chain intact:', ok)
"

# 5. Generate compliance report
PYTHONPATH="." python tools/verify_compliance.py --all \
  --circuit CIRCUIT_NAME \
  --report --output data/compliance_report_post_race.json

# 6. Archive race data
RACE_DATE=$(date +%Y%m%d)
mkdir -p archive/race_${RACE_DATE}
cp -r data/reports/ archive/race_${RACE_DATE}/
cp data/compliance_report_post_race.json archive/race_${RACE_DATE}/

# 7. Commit archive (NOT raw telemetry)
git add archive/race_${RACE_DATE}/ data/reports/
git commit -m "chore: post-race archival $(date +%F) — ${RACE_DATE}"
```

### Post-Race Archival Checklist

| # | Task | Pass Criterion |
|---|------|----------------|
| 20 | Edge buffer drained | Pending count = 0 |
| 21 | DLQ reprocessed | Schema drift recovered |
| 22 | Audit chain verified | `True` |
| 23 | SLO report generated | All 6 SLOs documented |
| 24 | Compliance report saved | File present |
| 25 | Data archived | `archive/race_YYYYMMDD/` created |
| 26 | Git commit clean | No raw telemetry committed |

---

## 6. Steward Inquiry Readiness

The pipeline must be able to respond to FIA steward requests within **15 minutes**.

### Pre-Race Readiness Confirmation

```bash
# Verify steward package can be generated in < 15 minutes
time PYTHONPATH="." python tools/verify_compliance.py \
  --steward-package \
  --start 2026-01-01T00:00:00 \
  --end 2026-01-01T00:05:00 \
  --circuit CIRCUIT_NAME
```

Pass criterion: Command completes in < 60 seconds.

### During-Race Quick Inquiry

If stewards request data during the race:

```bash
PYTHONPATH="." python tools/verify_compliance.py \
  --steward-package \
  --start INCIDENT_START \
  --end INCIDENT_END \
  --circuit CIRCUIT_NAME \
  --output data/steward_inquiry_INCIDENT_ID.json
```

---

## 7. Triple-Header Operational Patterns

For weekends where three races occur in consecutive weekends (e.g., Spa → Zandvoort → Monza):

### Between-Weekend Procedure

| Day | Task |
|-----|------|
| Sunday (post-race) | Full archival, DLQ clear, audit verify |
| Monday | Analysis review, report generation |
| Tuesday | Hardware inspection, sensor recalibration |
| Wednesday | Pre-FP1 software checks for next circuit |
| Thursday | Arrive circuit, pre-race deployment checklist |
| Friday (FP1) | Live deployment |

### Carry-Over DLQ Management

After each race, reprocess all recoverable DLQ entries before the next circuit:

```bash
# Batch reprocess all recoverable packets
PYTHONPATH="." python -c "
from src.circuit_breaker import TelemetryCircuitBreaker
cb = TelemetryCircuitBreaker()
result = cb.reprocess_dlq(limit=100000)
print('Reprocessed:', result)
"
```

### Circuit-to-Circuit Firmware Check

Different circuits may run different ECU firmware updates. Verify the alias table before each circuit:

```bash
python -c "
from src.sensor_profiles import FIRMWARE_COMPAT_MATRIX, get_sensor_profile
# Identify which firmware version maps current sensor field names
for fw, mapping in FIRMWARE_COMPAT_MATRIX.items():
    print(f'{fw}: {list(mapping.keys())[:3]}...')
"
```

---

## 8. Deployment Sign-Off

All items from the following sections must be checked before FP1 green flag:

| Section | Items | Sign-Off |
|---------|-------|----------|
| 1. Pre-FP1 Validation | 1–14 | ⬜ Data Acquisition Engineer |
| 2. Sensor Calibration | All calibration items | ⬜ Data Acquisition Engineer |
| 3. Pit Wall Readiness | 15–19 | ⬜ Pit Wall Engineer |
| Compliance check | All compliance items | ⬜ Data Acquisition Lead |

```
Race Weekend: ________________________
Circuit: _____________________________
FP1 Date/Time: _______________________

Data Acquisition Engineer: ___________________  Sign-off: ___________
Pit Wall Engineer: __________________________ Sign-off: ___________
Data Acquisition Lead: ______________________ Sign-off: ___________
```

---

*See also:*
- [RACE_WEEKEND_RUNBOOK.md](RACE_WEEKEND_RUNBOOK.md) — Live incident response procedures
- [PIT_WALL_INTEGRATION.md](PIT_WALL_INTEGRATION.md) — Pit wall API and alert schema
- [COMPLIANCE_VERIFICATION.md](COMPLIANCE_VERIFICATION.md) — FIA and GDPR compliance guide
- [GPU_PERFORMANCE_BENCHMARKS.md](GPU_PERFORMANCE_BENCHMARKS.md) — Infrastructure justification
