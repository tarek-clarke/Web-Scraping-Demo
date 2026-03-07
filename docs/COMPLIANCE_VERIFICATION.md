# Compliance & Governance Verification

**System:** Resilient RAP Framework — Cadillac F1 Telemetry Pipeline  
**Version:** 2.0 — 2026 Season  
**Standards:** FIA Technical Regulations 2026 | GDPR (EU 2016/679) | UK GDPR

---

## Table of Contents

1. [Overview](#1-overview)
2. [Jurisdiction Mapping — 2026 F1 Calendar](#2-jurisdiction-mapping--2026-f1-calendar)
3. [GDPR Compliance Checklist](#3-gdpr-compliance-checklist)
4. [FIA Audit Trail Requirements](#4-fia-audit-trail-requirements)
5. [Automated Compliance Verification](#5-automated-compliance-verification)
6. [Post-Incident Forensics for Steward Inquiries](#6-post-incident-forensics-for-steward-inquiries)
7. [Compliance Verification CLI](#7-compliance-verification-cli)

---

## 1. Overview

The Resilient RAP framework implements **compliance by default** for the 2026 F1 season:

| Compliance Area | Implementation | Module |
|----------------|---------------|--------|
| GDPR PII scrubbing | Automatic for EU circuits | `src/geo_fence.py` |
| Data sovereignty | Jurisdiction-aware routing | `src/geo_fence.py` |
| FIA tamper-evidence | SHA-256 hash-chain audit log | `src/audit_log.py` |
| Steward inquiry data | DLQ + full provenance archive | `src/circuit_breaker.py` |
| Data minimisation | Only required fields transmitted | `SchemaValidator` |

---

## 2. Jurisdiction Mapping — 2026 F1 Calendar

The geo-fence module (`src/geo_fence.py`) applies jurisdiction-aware data handling per circuit:

| Circuit | Country | Jurisdiction | GDPR Applies | PII Scrubbing |
|---------|---------|-------------|-------------|--------------|
| Albert Park | Australia | AU | No | No |
| Bahrain International | Bahrain | BH | No | No |
| Jeddah Corniche | Saudi Arabia | SA | No | No |
| Suzuka | Japan | JP | No | No |
| Shanghai | China | CN | No | No |
| Miami International | USA | US | No | No |
| Imola | Italy | EU | **Yes** | **Yes** |
| Monaco | Monaco | EU | **Yes** | **Yes** |
| Circuit de Cataluña | Spain | EU | **Yes** | **Yes** |
| Circuit Gilles Villeneuve | Canada | CA | No | No |
| Red Bull Ring | Austria | EU | **Yes** | **Yes** |
| Silverstone | UK | UK-GDPR | **Yes** | **Yes** |
| Hungaroring | Hungary | EU | **Yes** | **Yes** |
| Spa-Francorchamps | Belgium | EU | **Yes** | **Yes** |
| Zandvoort | Netherlands | EU | **Yes** | **Yes** |
| Monza | Italy | EU | **Yes** | **Yes** |
| Baku City Circuit | Azerbaijan | AZ | No | No |
| Marina Bay | Singapore | SG | No | No |
| Circuit of the Americas | USA | US | No | No |
| Autódromo Hermanos Rodríguez | Mexico | MX | No | No |
| Interlagos | Brazil | BR | No | No |
| Las Vegas Strip Circuit | USA | US | No | No |
| Lusail International | Qatar | QA | No | No |
| Yas Marina | Abu Dhabi | AE | No | No |

> **Driver biometrics** (`heart_rate`) are classified as PII under GDPR Article 9 (special category health data).  
> At EU/UK circuits, driver biometric fields are **scrubbed from cloud-bound records** but preserved in the local trackside edge buffer for race operations.

### Jurisdiction Check

```python
from src.geo_fence import GeoFence, CIRCUIT_JURISDICTION

geo = GeoFence()

# Check jurisdiction for a circuit
jurisdiction = CIRCUIT_JURISDICTION.get("monaco")
print(jurisdiction)  # "EU"

# Validate current circuit config
geo.validate_config()  # raises if misconfigured

# Process a packet with jurisdiction-aware handling
sanitised = geo.process(packet, circuit="monaco")
```

---

## 3. GDPR Compliance Checklist

### Per-Race Weekend Checklist (EU/UK Circuits)

| # | Requirement | Implementation | Verified By |
|---|------------|---------------|------------|
| 1 | PII scrubbing active for EU circuit | `GeoFence.process()` | `tools/verify_compliance.py --check gdpr` |
| 2 | Driver biometrics not in cloud records | `heart_rate` field scrubbed | Audit log inspection |
| 3 | Data minimisation — only required fields | `SchemaValidator` field list | Schema config review |
| 4 | Local edge buffer not transmitted cross-border | SQLite write-local-first | Architecture review |
| 5 | Audit trail available for Subject Access Request | Hash-chain log | `tools/verify_compliance.py --check sar` |
| 6 | Data retention policy applied | DLQ TTL configuration | `verify_compliance.py` |
| 7 | Geo-fence config loaded and validated | `GeoFence().validate_config()` | Pre-race checklist §1 |
| 8 | No PII in unencrypted cloud transit | TLS enforced on Kafka | Infrastructure review |

### Data Subject Rights

The framework supports GDPR Article 17 (Right to Erasure) and Article 15 (Right of Access):

```bash
# Generate data subject access report for a driver
python tools/verify_compliance.py --sar-export --driver-id DRV_001 \
  --output data/sar/driver_001_access_report.json

# Erase biometric data for a driver (post-season)
python tools/verify_compliance.py --erase-biometrics --driver-id DRV_001 \
  --confirm
```

---

## 4. FIA Audit Trail Requirements

### FIA Technical Regulation Requirements (2026)

| Requirement | Regulation Ref | Implementation |
|-------------|---------------|---------------|
| All telemetry transformations logged | Art. 8.3 | `src/audit_log.py` hash chain |
| Tamper-evident records | Art. 8.4 | SHA-256 linked chain |
| Data available for 5 years | Art. 8.5 | Archive to `archive/race_YYYYMMDD/` |
| Steward access within 15 minutes | Art. 8.6 | `tools/verify_compliance.py --steward-package` |
| No data modification after race end | Art. 8.7 | Write-once DLQ records |

### Audit Chain Verification

```python
from src.audit_log import AuditLog, ComplianceAuditLog

al = AuditLog()

# Full chain verification
chain_intact = al.verify_chain()
print("Audit chain intact:", chain_intact)

# Export chain for FIA submission
al.export_chain(output_path="data/fia_audit_chain.json")
```

### Hash-Chain Structure

Each telemetry transformation creates an audit record:

```json
{
  "id": 1234,
  "timestamp": "2026-05-25T14:32:17.843Z",
  "event_type": "schema_drift_recovery",
  "sensor": "engine_temp",
  "input_hash": "sha256:ab3f7d...",
  "output_hash": "sha256:cd91e2...",
  "previous_hash": "sha256:9fa3b1...",
  "transformation": "field_alias_normalisation: TwaterOut → engine_temp",
  "firmware_version": "fw_2025_pre",
  "operator": "automated_bert_reconciler"
}
```

The chain is broken if `previous_hash` of record N ≠ `output_hash` of record N-1.

---

## 5. Automated Compliance Verification

Run the compliance verification tool before every race weekend:

```bash
# Full compliance check
python tools/verify_compliance.py --all

# GDPR check only
python tools/verify_compliance.py --check gdpr --circuit monaco

# FIA audit trail check
python tools/verify_compliance.py --check fia

# Generate compliance report
python tools/verify_compliance.py --report --output data/compliance_report.json
```

### Expected Output

```
╔══════════════════════════════════════════════════════════════╗
║          CADILLAC F1 COMPLIANCE VERIFICATION                  ║
║          2026 Season — Pre-Race Check                        ║
╚══════════════════════════════════════════════════════════════╝

Circuit: Monaco (Jurisdiction: EU)

GDPR Compliance
  [✅] Geo-fence config loaded
  [✅] PII scrubbing active for EU circuit
  [✅] heart_rate excluded from cloud records
  [✅] Data minimisation — 15 sensor fields configured
  [✅] Audit log available for SAR requests

FIA Audit Trail
  [✅] Audit chain intact (2,847 records verified)
  [✅] No gaps in hash chain sequence
  [✅] Last record: 2026-05-25T14:31:00Z
  [✅] Archive present: archive/race_20260525/

Data Sovereignty
  [✅] Local edge buffer write-first confirmed
  [✅] No cross-border transmission during connectivity test
  [✅] SQLite WAL mode active

Overall: 14/14 checks PASSED ✅
Report saved: data/compliance_report_20260525.json
```

---

## 6. Post-Incident Forensics for Steward Inquiries

### Steward Inquiry Workflow

When the FIA stewards request telemetry data for an incident:

```
Incident reported by stewards
        │
        ▼
1. Identify incident time window (from steward notice)
        │
        ▼
2. python tools/verify_compliance.py --steward-package \
          --start "2026-05-25T14:30:00" \
          --end "2026-05-25T14:35:00"
        │
        ▼
3. Package generated: data/steward_inquiry_YYYYMMDD_HHMMSS.json
        │
        ▼
4. Package submitted to FIA via official channel (< 15 min SLO)
        │
        ▼
5. Stewards verify SHA-256 hash chain independently
```

### Steward Package Contents

The `--steward-package` command generates a JSON archive containing:

- All telemetry packets in the requested time window
- DLQ records (rejected packets) in the same window
- SHA-256 hash chain proof covering the entire window
- Geo-fence audit: confirmation of jurisdiction and PII handling
- Firmware version at time of incident
- Circuit breaker state history during the window

### Sample Steward Package Schema

```json
{
  "inquiry_id": "FIA-2026-025-001",
  "generated_at": "2026-05-25T14:44:12Z",
  "requested_window": {
    "start": "2026-05-25T14:30:00Z",
    "end": "2026-05-25T14:35:00Z"
  },
  "circuit": "monaco",
  "jurisdiction": "EU",
  "hash_chain_verified": true,
  "hash_chain_records": 1247,
  "packet_count": 18450,
  "dlq_count": 234,
  "pii_scrubbing_active": true,
  "firmware_version": "fw_2026_launch",
  "packets": [ ... ],
  "dlq_records": [ ... ],
  "audit_chain_excerpt": [ ... ]
}
```

---

## 7. Compliance Verification CLI

The `tools/verify_compliance.py` CLI provides all compliance operations:

```
Usage: python tools/verify_compliance.py [OPTIONS]

Options:
  --all                   Run all compliance checks
  --check [gdpr|fia|sovereignty]
                          Run a specific check category
  --circuit CIRCUIT       Circuit name for jurisdiction lookup
  --report                Generate JSON compliance report
  --output PATH           Output path for report
  --steward-package       Generate FIA steward inquiry package
  --start DATETIME        Start of steward inquiry window (ISO 8601)
  --end DATETIME          End of steward inquiry window (ISO 8601)
  --sar-export            Export Subject Access Request data
  --driver-id ID          Driver identifier for SAR export
  --erase-biometrics      Erase biometric data (requires --confirm)
  --confirm               Confirm destructive operations
  --db-path PATH          SQLite database path (default: data/telemetry.db)
  --audit-log PATH        Audit log path (default: data/provenance_log.jsonl)
  --help                  Show this message and exit

Examples:
  python tools/verify_compliance.py --all --circuit monaco
  python tools/verify_compliance.py --check fia --report --output data/fia_check.json
  python tools/verify_compliance.py --steward-package --start 2026-05-25T14:30:00 --end 2026-05-25T14:35:00
```

See `tools/verify_compliance.py` for the full implementation.
