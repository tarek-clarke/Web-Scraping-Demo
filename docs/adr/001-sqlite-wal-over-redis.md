# ADR-001: SQLite WAL over Redis for Trackside Edge Buffer

**Status:** Accepted  
**Date:** 2026-01-15  
**Decision-makers:** Tarek Clarke  

## Context

The trackside edge buffer must persist every telemetry packet locally before
attempting a cloud sync.  Two candidates were evaluated:

| Criteria | SQLite WAL | Redis |
|----------|-----------|-------|
| **Zero-dependency deployment** | Single file on disk — no daemon | Requires a running Redis server |
| **Crash recovery** | WAL journaling survives power loss | AOF/RDB persistence is tunable but adds operational complexity |
| **Portability** | Ships with Python (`sqlite3` stdlib) | Requires `redis-py` + server binary |
| **Bandwidth at trackside** | Zero network overhead (local file) | Loopback traffic; adds latency under load |
| **Exactly-once drain** | `UPDATE … SET status='SYNCED' WHERE id IN (…)` in a single transaction | Requires Lua scripts or WATCH/MULTI for atomicity |
| **Post-race forensics** | `.sqlite` file is self-contained, portable, easily archived | Requires RDB snapshot export |

## Decision

Use **SQLite in WAL mode** as the sole persistence engine for the trackside
edge buffer.

## Rationale

1. **Zero infrastructure at the track.**  The pit wall runs on portable
   hardware.  Adding a Redis daemon increases the failure surface with no
   measurable benefit for a single-writer workload.

2. **Exactly-once batch semantics are trivial in SQL.**  A single
   `BEGIN IMMEDIATE` transaction marks drained rows as `SYNCED` and commits
   atomically.  Redis requires multi-step scripts for equivalent guarantees.

3. **Post-race archival.**  A `.sqlite` file can be copied to cold storage
   and queried years later without standing up infrastructure.  This matters
   for FIA regulatory audits.

4. **Performance is sufficient.**  At 50 Hz telemetry (the maximum car
   downlink rate), SQLite WAL sustains >10 000 inserts/sec on commodity
   hardware — well within margin.

## Consequences

- **Pro:** Minimal operational footprint; single dependency (Python stdlib).
- **Pro:** Crash-safe by default; WAL survives unexpected power loss.
- **Con:** Not horizontally scalable.  If the pipeline ever moves to
  multi-car ingest on separate machines, a networked store will be needed.
  This is acceptable because the current architecture is single-car-per-node
  by design (each car has its own edge buffer instance).

## References

- SQLite WAL documentation: https://www.sqlite.org/wal.html
- `src/local_persistence.py` — implementation
