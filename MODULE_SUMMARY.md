# Module Summary - Telemetry Platform Telemetry Spine

## Core Pipeline Modules

---

### **src/circuit_breaker.py** (557 lines)
**Purpose:** Three-state FSM that protects the pipeline from corrupted telemetry.

**Key Classes:**
- `TelemetryCircuitBreaker` — Main breaker with CLOSED/OPEN/HALF_OPEN states
- `SchemaValidator` — Validates sensor types and physically plausible ranges (15+ F1 sensors)
- `DeadLetterQueue` — SQLite-backed quarantine for rejected packets
- `CircuitBreakerMetrics` — Live metrics exposed to health monitor

**Why it matters:**
- One bad sensor (e.g., 5000°C engine temp from a bit-flip) can corrupt lap analysis. The breaker catches it.
- HALF_OPEN probing allows automatic recovery without manual pit-wall intervention.
- DLQ reprocessing enables recovery after firmware updates or sensor calibration fixes.

**Key implementation:**
- State transitions are guarded by a lock (thread-safe under 5k pps)
- `reprocess_dlq(limit=100)` lets you recover quarantined packets after fixing the underlying issue
- `metrics` property exposes uptime ratio, consecutive failures, and DLQ depth for monitoring

---

### **src/local_persistence.py** (370 lines)
**Purpose:** Trackside edge buffer that guarantees zero data loss during connectivity drops.

**Key Classes:**
- `TracksideEdgeBuffer` — SQLite WAL-backed local buffer
- `BufferedPacket` — Schema for persisted telemetry
- `SyncStatus` — Enum (PENDING, SYNCED, FAILED, DRAINING)

**Why it matters:**
- WiFi at the track drops. Packets must survive locally until uplink recovers.
- RPO = 0 packets lost. Every packet is committed to disk before any cloud sync is attempted.
- RTO < 5s. Background drain thread automatically resumes and syncs pending batches.

**Key implementation:**
- **Exactly-once batch semantics:** 3-phase drain (claim PENDING rows → sync → ACK/rollback)
- Batch IDs track state: DRAINING → ACKED/FAILED/RECOVERED
- `recover_incomplete_batches()` on startup handles process crashes during drain
- `drain_history` property shows recent batch status for observability

---

### **src/geo_fence.py** (358 lines)
**Purpose:** Jurisdiction-aware processor that enforces GDPR/data sovereignty rules.

**Key Classes:**
- `GeoFence` — Per-circuit compliance enforcer
- `Jurisdiction` — Enum (EU, US, ME, APAC, UK)
- `JurisdictionPolicy` — Rule set per jurisdiction
- `GeoFenceResult` — Separate local_payload (full data) vs sync_payload (compliant data)

**Why it matters:**
- EU rounds must scrub PII, anonymize biometrics, retain locally. US rounds can send full telemetry.
- Compliance isn't optional. It's wired into the pipeline.
- Every compliance action is logged immutably (see audit_log below).

**Key implementation:**
- Barcelona → EU policy → PII scrubbed, biometrics anonymized, metadata-only sync
- Austin → US policy → full telemetry forwarded
- Request-ID propagated through geo-fence for end-to-end tracing
- Each result includes `compliance_hash` (SHA-256) as proof of processing

---

### **src/audit_log.py** (309 lines)
**Purpose:** Immutable, hash-chained audit trail for every compliance decision.

**Key Classes:**
- `ComplianceAuditLog` — Append-only SQLite with SHA-256 chain links
- `AuditEntry` — Single immutable record (action, circuit, jurisdiction, request_id, details)

**Why it matters:**
- GDPR auditors demand proof that PII was handled correctly. This log provides it.
- `verify_chain()` detects tampering — each entry's hash includes the previous entry's hash.
- Query by jurisdiction or request_id for full compliance trace.

**Key implementation:**
- Append-only DDL (no UPDATE/DELETE permitted in schema)
- Each entry: `chain_hash = SHA-256(prev_hash || json(entry_data))`
- Indexes on `action`, `circuit`, `jurisdiction`, `request_id` for fast queries
- `query_by_request_id()` traces a single packet through all compliance steps

---

### **src/middleware/tracing.py** (130 lines)
**Purpose:** Request-ID correlation and per-stage latency tracking.

**Key Classes:**
- `RequestContext` — Immutable context that flows through the pipeline
- `TraceStage` — Single pipeline stage with status and latency_ms

**Why it matters:**
- When a packet fails, trace it end-to-end: breaker → buffer → geo-fence → cloud
- Latency profiling at each stage identifies bottlenecks.
- Correlation ID ties together async operations (breaker → buffer drain → cloud ACK).

**Key implementation:**
- `add_stage(stage, status, details)` records stage entry and measures latency from previous stage
- `trace_summary()` returns JSON-serializable dict for logging/debugging
- `is_failed` property detects if any stage returned REJECTED/FAILED/ERROR

---

## Infrastructure & Observability

---

### **tools/telemetry_stress_test.py** (605 lines)
**Purpose:** Triple-header stress test simulating real F1 load with chaos injection.

**Simulates:**
- 3 race weekends × 5 sessions = 15 total sessions
- 1,000+ packets/session with realistic sensor ranges
- 7 chaos modes: null_value, string_in_numeric, bit_flip_high/low, schema_drift, dropout, dup timestamp

**Output:**
- **Resilience Score:** Weighted composite (clean throughput 35% + corruption detection 25% + recovery 20% + latency 20%)
- CSV/JSON reports with per-session metrics
- Live Rich TUI progress bar
- DLQ depth, breaker trips, audit chain integrity in final report

**Key metrics:**
- p95 latency target: <100ms (trackside requirement)
- Corruption detection: 100% of chaos should be caught
- Zero duplicates: exactly-once batch semantics proven

---

### **tools/health_monitor.py** (477 lines)
**Purpose:** Real-time pit-wall dashboard showing live pipeline health.

**Displays:**
- **Latency percentiles** (p50, p95, p99) updated every 2 seconds
- **Circuit Breaker state** (CLOSED/OPEN/HALF_OPEN) with failure count
- **DLQ depth** (quarantined packets)
- **Edge Buffer health** (pending sync, synced, failed, utilization %)
- **Drift alerts** (schema or value range anomalies)

**Key UX:**
- Live Rich TUI with color coding (green = healthy, red = alert)
- Refresh interval configurable (default 2s)
- No pit-wall engineer needs to SSH into the box — all data on one screen

---

## Infrastructure & Deployment

---

### **Dockerfile.production** (57 lines)
**Purpose:** Multi-stage, non-root, read-only container for security.

**Security Model:**
- Build stage (Python, deps) never reaches runtime image
- Runtime runs as UID 1000 (non-root)
- Read-only filesystem prevents accidental overwrites
- HEALTHCHECK validates import-readiness before traffic flows

**Why it matters:**
- Budget Cap era demands security discipline. No root exploits in containers.
- Immutable infrastructure — if the pod is running correctly now, it will run correctly at 2am on race day.

---

### **docker-compose.production.yml** (145 lines)
**Purpose:** Orchestration with resource limits and network isolation.

**Architecture:**
- 3 services: pipeline (main), health-monitor (observability), edge-buffer (persistence)
- Internal bridge network (`telemetry-internal`) — no external exposure
- CPU/memory limits enforced (Budget Cap discipline)
- Secrets NOT in image (env vars only)

---

## Testing

---

### **tests/test_telemetry_modules.py** (388 lines, 59 tests)
**Coverage:**

| Module | Tests | Coverage |
|--------|-------|----------|
| SchemaValidator | 6 | Valid packets, null values, out-of-range, unknown sensors |
| DeadLetterQueue | 3 | Enqueue, depth, mark_reprocessed |
| CircuitBreaker | 7 | CLOSED/OPEN/HALF_OPEN transitions, batch processing, reset, metrics |
| TracksideEdgeBuffer | 6 | Write/replay, batch dedup, drain callbacks, health metrics |
| GeoFence | 9 | Per-jurisdiction scrubbing, anonymization, compliance hash |
| **NEW:** ComplianceAuditLog | 8 | Record, hash-chain integrity, tamper detection, jurisdiction queries, chain resumption |
| **NEW:** GeoFence+Audit | 5 | EU processing creates audit entries, US skips audit, export-control marked |
| **NEW:** DLQReprocessing | 5 | Range recovery, retry limits, fetch_reprocessable |
| **NEW:** ExactlyOnceDrain | 5 | Batch IDs, rollback on failure, crash recovery, drain history |
| **NEW:** RequestTracing | 5 | Context creation, stage tracking, latency measurement |

**All passing:** 59/59 ✅

---

## Quick Reference: What to Emphasize

| Question | Answer | Module |
|----------|--------|--------|
| *What prevents data loss?* | SQLite WAL + exactly-once batch semantics + crash recovery | local_persistence.py |
| *What stops bad data from corrupting analysis?* | Three-state circuit breaker + SchemaValidator + DLQ reprocessing | circuit_breaker.py |
| *How do we handle GDPR?* | Per-circuit geo-fence, immutable audit log, verifiable chain | geo_fence.py + audit_log.py |
| *How do we trace failures?* | Request-ID correlation + per-stage latency tracking | tracing.py |
| *How do we prove it works?* | Chaos injection stress test, 59 unit/integration tests, resilience scoring | telemetry_stress_test.py + tests/ |
| *What happens at 2am on race day?* | Health monitor on one screen, alert thresholds, auto-recovery | health_monitor.py |


