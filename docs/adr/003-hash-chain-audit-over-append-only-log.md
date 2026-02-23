# ADR-003: SHA-256 Hash-Chain Audit Log over Append-Only Flat File

**Status:** Accepted  
**Date:** 2026-01-22  
**Decision-makers:** Tarek Clarke  

## Context

The FIA requires demonstrable data provenance for any telemetry used in
budget-cap submissions or post-race analyses.  Two approaches were
evaluated for tamper-evident audit logging:

| Approach | Tamper evidence | Query capability | Portability |
|----------|----------------|-----------------|-------------|
| **Append-only flat file** (JSONL) | None — any line can be edited silently | Requires full scan or external index | Simple copy |
| **SHA-256 hash chain in SQLite** | Each entry's hash includes the previous entry's hash — any modification breaks the chain | SQL queries by timestamp, event type, or hash | Self-contained `.sqlite` file |

## Decision

Use a **SHA-256 hash-chained audit log** stored in SQLite, where each record
includes `previous_hash` and `entry_hash = SHA256(previous_hash ‖ payload)`.

## Rationale

1. **Tamper detection is cryptographic, not procedural.**  If any row in the
   chain is modified, the hash discontinuity is detectable by recomputing
   the chain from the genesis record.  This provides stronger guarantees
   than file permissions or write-once storage alone.

2. **Regulatory defensibility.**  In the event of an FIA audit, the team can
   provide the `.sqlite` file and a verification script.  The auditor
   independently walks the chain — no proprietary tools needed.

3. **Queryability.**  Unlike a flat file, the SQLite store supports indexed
   lookups by timestamp or event type, which is critical for post-race
   forensics ("show me every geo-fence decision for the Barcelona weekend").

4. **Composability with existing modules.**  The edge buffer and DLQ already
   use SQLite.  Adding the audit log to the same storage layer avoids
   introducing a new dependency.

## Consequences

- **Pro:** Cryptographic tamper evidence satisfies the strictest reasonable
  interpretation of FIA data-provenance requirements.
- **Pro:** SQL queries make forensic investigation fast and scriptable.
- **Con:** Hash-chain verification is O(n) in the number of entries.  For
  a full season (~24 races × ~5 sessions × ~100 000 packets), this is
  ~12 M entries — verification takes seconds on modern hardware, which is
  acceptable for an offline audit.
- **Con:** The chain is linear (not a Merkle tree), so verification cannot
  be parallelised.  This is a deliberate simplicity trade-off; a Merkle
  tree adds implementation complexity with no practical benefit at the
  expected data volumes.

## References

- NIST SP 800-185 (SHA-3 derived functions): precedent for hash-chain integrity
- `src/audit_log.py` — implementation
- `src/provenance.py` — complementary provenance tracking
