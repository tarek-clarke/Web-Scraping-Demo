# A Resilient Pipeline for Cadillac F1: A Research-to-Production Spine

[![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen)](.)
![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial-red.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)
![Docker](https://img.shields.io/badge/Docker-Enterprise--Hardened-blue)
[![PhD Research](https://img.shields.io/badge/PhD-TalTech%20RAP%20Research-purple)](.)


Developed for the **2026 Cadillac F1 Initiative**.

---

**Background:** 10+ years as a Senior Data Engineer at Statistics Canada, shipping production pipelines that handle the country's most sensitive data at scale.  That same discipline — tamper-evident lineage, automated reconciliation, zero-tolerance for data corruption — is exactly what the F1 Budget Cap era demands.

**The Academic Edge:** This is the production-ready implementation of my upcoming PhD research at TalTech (Tallinn University of Technology) on **Reproducible Analytical Pipelines (RAP)** for high-velocity sensor telemetry.  Every module in this repository traces back to a peer-reviewed methodology for autonomous schema drift resolution.

**The Value Proposition:** Self-healing code reduces the headcount needed for trackside IT support.  Instead of flying a team of data engineers to every race, the pit wall gets a pipeline that detects corruption, isolates bad packets, and recovers — all without human intervention.  In the Budget Cap era, that's not just engineering, it's a competitive advantage.

---

## Architecture

```
                         ┌──────────────────────────────────┐
                         │        CAR RF DOWNLINK            │
                         └───────────────┬──────────────────┘
                                         │
                         ┌───────────────▼──────────────────┐
                         │     CIRCUIT BREAKER (Schema Guard)│
                         │  ┌─────────┐    ┌─────────────┐  │
                         │  │ CLOSED  │───►│ Validator    │  │
                         │  │ (relay) │    │ (bit-flip,   │  │
                         │  └────┬────┘    │  drift, NaN) │  │
                         │       │         └──────┬──────┘  │
                         │       │ ◄──OPEN──┐     │         │
                         │       │          │     │         │
                         │       ▼        ┌─▼─────▼──┐      │
                         │  ┌─────────┐   │   DLQ    │      │
                         │  │HALF_OPEN│   │ (SQLite) │      │
                         │  │ (probe) │   └──────────┘      │
                         │  └─────────┘                     │
                         └───────────────┬──────────────────┘
                                         │ clean packets
                         ┌───────────────▼──────────────────┐
                         │   TRACKSIDE EDGE BUFFER (SQLite)  │
                         │   Local-First • Zero Data Loss    │
                         └───────────────┬──────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │          GEO-FENCE (GDPR / Sovereignty)  │
                    │  EU rounds: PII scrubbed, local retain   │
                    │  US rounds: full telemetry to War Room   │
                    └────────────────────┬────────────────────┘
                                         │
               ┌─────────────────────────▼──────────────────────┐
               │        SEMANTIC RECONCILIATION (BERT)           │
               │   Schema-on-Read • Autonomous Field Mapping     │
               └─────────────────────────┬──────────────────────┘
                                         │
                         ┌───────────────▼──────────────────┐
                         │     GLOBAL SINK (War Room)        │
                         │  Tamper-Evident Provenance Chain   │
                         └──────────────────────────────────┘
```

---


## Key Capabilities

| Capability | Module | Evidence |
|---|---|---|
| **Zero data loss** during trackside connectivity drops | `src/local_persistence.py` | SQLite WAL edge buffer persists every packet locally before cloud sync |
| **Local-first** architecture — pit wall always has full telemetry | `TracksideEdgeBuffer` | Full local replay available even when uplink is severed |
| **Automatic background drain** when connectivity is restored | `start_background_drain()` | Daemon thread syncs pending packets in configurable batches |
| **Production health checks** in Docker | `docker-compose.production.yml` | `HEALTHCHECK` ensures pipeline is import-ready before traffic flows |
| **Circuit-Breaker pattern** isolates bad telemetry to DLQ | `src/circuit_breaker.py` | Three-state FSM (CLOSED → OPEN → HALF_OPEN) with configurable thresholds |
| **Schema-on-Read guarantee** — simulation models never fed garbage | `SchemaValidator` | Validates sensor types, value ranges, and physically plausible bounds |
| **Dead Letter Queue** — quarantined packets available for post-race forensics | `DeadLetterQueue` (SQLite) | Thread-safe, indexed by sensor and timestamp |
| **Bit-flip detection** on `ecu_canbus` and `aero_load` sensors | `DEFAULT_RANGES` config | Catches impossible values (e.g. 5000°C engine temp, negative tyre pressure) |
| **BERT semantic reconciliation** handles firmware-level schema drift | `SemanticTranslator` | Cosine similarity mapping from corrupted field names to gold standard |
| **Geo-Fencing / Data Sovereignty** for EU ↔ US compliance | `src/geo_fence.py` | Per-circuit jurisdiction mapping (2026 calendar), GDPR PII scrubbing |
| **Multi-stage Docker** — build deps never reach runtime | `Dockerfile.production` | Non-root user (UID 1000), read-only FS, no-new-privileges |
| **Resource limits** — Budget Cap discipline in infrastructure | `docker-compose.production.yml` | CPU/memory caps, tmpfs for ephemeral writes |
| **Network isolation** — internal bridge network for pipeline services | `cadillac-internal` network | No external exposure; secrets never in image layers |
| **Tamper-evident audit** — SHA-256 hash chains for every transformation | `src/provenance.py` | Linked `input_hash → output_hash → previous_hash` records |

---

## Quick Start — Cadillac F1 Production

### Local Development

```bash
# 1. Environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. One-click showcase (runs everything — tests, stress test, health monitor, demos)
./tools/run_cadillac_showcase.sh

# 3. Or run individual subsystems:

# Stress test — showcase mode (1000 pkt × 15 sessions, 10% chaos)
PYTHONPATH="." python3 tools/cadillac_stress_test.py --showcase

# Stress test — full load (custom packets and chaos rate)
PYTHONPATH="." python3 tools/cadillac_stress_test.py --packets 5000 --chaos 0.20

# Health Monitor (live pit wall dashboard, 30s demo)
PYTHONPATH="." python3 tools/health_monitor.py --duration 30

# Test suite
PYTHONPATH="." pytest tests/test_cadillac_modules.py -v
```

### Docker (Production)

```bash
# Build and run the stress test
docker compose -f docker-compose.production.yml up --build stress-test

# Run the health monitor
docker compose -f docker-compose.production.yml up --build health-monitor

# Deploy the pipeline
docker compose -f docker-compose.production.yml up telemetry-spine
```

---

## Core Demonstrations

### Circuit-Breaker + Dead Letter Queue

```bash
PYTHONPATH="." python3 tools/cadillac_stress_test.py --showcase
```

Triple-Header simulation: 3 race weekends × 5 sessions × 1000 packets with 10% chaos injection (showcase mode).  
For heavier load testing, use `--packets 5000 --chaos 0.20`.

**Validates:**
- Circuit-breaker trips when consecutive failures exceed threshold
- Breaker recovers after cooldown (HALF_OPEN probe)
- Bad packets routed to SQLite DLQ
- Pit wall feed remains clean

### Trackside Edge Buffer (Zero Data Loss)

```python
from src.local_persistence import TracksideEdgeBuffer, BufferedPacket

buffer = TracksideEdgeBuffer(db_path="data/edge_buffer.sqlite", max_buffer_size=100_000)
buffer.start_background_drain(interval=5.0)  # Auto-sync every 5s

# Every packet persists locally first
packet = BufferedPacket(sensor="speed", value=350.0)
buffer.write(packet)

# Full replay available even if cloud link is down
replay = buffer.replay(session_id="silverstone_race", limit=1000)
```

### Geo-Fencing (Data Sovereignty)

```python
from src.geo_fence import GeoFence

geo = GeoFence()

# Barcelona (EU) → PII scrubbed, local-retained
result_eu = geo.process(
    circuit="barcelona",
    payload={"heart_rate": 165, "driver_name": "Max", "speed": 320}
)
print(result_eu.sync_payload)  # heart_rate → anonymized, driver_name → [REDACTED]
print(result_eu.local_payload)  # Full data retained on EU sovereign storage

# Austin (US) → full telemetry to War Room
result_us = geo.process(
    circuit="austin",
    payload={"heart_rate": 165, "driver_name": "Max", "speed": 320}
)
print(result_us.sync_payload)  # All fields intact
```

### Health Monitor (Pit Wall Dashboard)

```bash
PYTHONPATH="." python3 tools/health_monitor.py
```

Live terminal UI showing:
- Circuit-Breaker state (CLOSED / OPEN / HALF_OPEN)
- Edge Buffer health (pending sync, utilisation)
- Latency percentiles (p50 / p95 / p99)
- Drift alerts (schema corruption events)
- Geo-Fence compliance status

---

## The Full Showcase Suite (Original RAP Research)

Run everything with one command:

```bash
./tools/run_cadillac_showcase.sh
```

Or execute individual stages:

### Step 1 — F1 Telemetry (OpenF1 API)
```bash
PYTHONPATH="." python3 tools/demo_openf1.py --session 9158 --driver 1
```

### Step 2 — Engine Temperature Stress Test
```bash
PYTHONPATH="." python3 tools/stress_test_engine_temp.py
```

### Step 3 — Semantic Layer Benchmark
```bash
PYTHONPATH="." python3 tools/benchmark_semantic_layer.py
```

### Step 4 — PDF Audit Report
```bash
PYTHONPATH="." python3 tools/demo_pdf_report.py
```

---

## Repository Structure

```
resilient-rap-framework/
├── src/
│   ├── circuit_breaker.py           # Circuit-Breaker + DLQ
│   ├── local_persistence.py         # Trackside Edge Buffer
│   ├── geo_fence.py                 #  Data Sovereignty / Geo-Fence
│   ├── provenance.py                # Tamper-Evident Logger
│   └── analytics/
├── modules/
│   ├── base_ingestor.py             # Core pipeline orchestrator
│   ├── translator.py                # BERT Semantic Translator
│   ├── enhanced_translator.py       # HITL-enhanced translator
│   ├── f1_telemetry_logger.py       # 50Hz telemetry simulation
│   └── ...
├── adapters/
│   ├── openf1/                      # Live F1 API adapter
│   └── ...
├── tools/
│   ├── cadillac_stress_test.py      # ⭐ Triple-Header Stress Test
│   ├── health_monitor.py            # ⭐ Pit Wall CLI Dashboard
│   ├── demo_openf1.py               # F1 telemetry demo
│   └── ...
├── tests/                           # Automated test suite
├── data/reports/                    # Generated reports & CSVs
├── Dockerfile.production            # ⭐ Enterprise-hardened image
├── docker-compose.production.yml    # ⭐ Production deployment
└── README.md                        # ← You are here
```

---

## The Budget Cap Argument

The 2026 F1 regulations impose strict budget caps.  Every person you fly to a race costs money.  Every manual data fix costs time.  This framework is designed to replace manual trackside IT triage with autonomous, self-healing code:

- **Schema drift?** The BERT translator handles it.
- **Sensor corruption?** The circuit breaker isolates it to the DLQ.
- **Connectivity drop?** The edge buffer holds everything.
- **EU data laws?** The geo-fence scrubs and retains.



---

## Testing

```bash
PYTHONPATH="." pytest tests/ -v
```

---

## Licensing

PolyForm Noncommercial License 1.0.0.  Commercial use requires separate agreement.

**Contact:** tclarke91@proton.me

---

<p align="center">
<strong>Tarek Clarke</strong> · Senior Data Analyst (StatCan) · Incoming PhD Candidate (TalTech)<br/>
Developed for the 2026 Cadillac F1 Initiative
</p>
