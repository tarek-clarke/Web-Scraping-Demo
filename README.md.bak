# Resilient RAP Framework

[![Status](https://img.shields.io/badge/Status-Prototype-blue)](https://img.shields.io/badge/Status-Prototype-blue)
![License](https://img.shields.io/badge/License-PolyForm%20Noncommercial-red.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)
[![Analytics](https://img.shields.io/badge/Analytics-Tracked_via_Scarf-blue)](https://about.scarf.sh)

A production-oriented framework for autonomous schema drift resolution in high-velocity sports telemetry (F1, NHL) and health telemetry (ICU).

## Production Capabilities

- Semantic reconciliation for schema drift using a BERT-based translator.
- Tamper-evident lineage and audit logging (SHA-256 linked records).
- HITL analytics for intervention cost and learning curves.
- Adapter-based ingestion for F1 telemetry, NHL play-by-play, and ICU streams.
- Deterministic, reproducible runs with run IDs and lineage checkpoints.

---

## Showcase Suite

A complete end-to-end demonstration sequence. Run each step in order for a full walkthrough of the framework's research contributions.

### Step 0 — Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Verify environment:

```bash
PYTHONPATH="." pytest tests/ -v
# Expected: 46 passed
```

---

### Step 1 — F1 Telemetry Pipeline (Schema Drift + Semantic Reconciliation)

Ingests live Formula 1 telemetry from the OpenF1 API. Demonstrates BERT-based autonomous field mapping when sensor tag names change between sessions.

```bash
PYTHONPATH="." python tools/demo_openf1.py --session 9158 --driver 1
```

**What to observe:**
- Incoming field names (`spd_kph_gps`, `eng_rpm_log`, etc.) are automatically mapped to the gold-standard schema using cosine similarity over BERT embeddings.
- Each mapping is recorded in the lineage trail with confidence scores.
- No manual field renaming required.

---

### Step 2 — NHL Play-by-Play Pipeline

Ingests structured game event data and reconciles schema variance across league data feeds.

```bash
PYTHONPATH="." python tools/demo_nhl.py --game 2024020001
```

**What to observe:**
- Same reconciliation pipeline applied to a completely different domain.
- Demonstrates domain-agnostic generalisation — a core research claim.

---

### Step 3 — Clinical ICU Stream (Health Telemetry)

Generates a synthetic multi-vendor ICU stream (GE, Philips, Dräger sensor naming conventions) and heals schema variance automatically.

```bash
PYTHONPATH="." python main.py --adapter clinical --export-audit --audit-path data/clinical_audit.json
```

**What to observe:**
- Vendor-specific tags (`hr_watch_01`, `spo2_philips_02`, `bp_sys_art_line`) are reconciled to standardised clinical labels.
- Demonstrates applicability to regulated, safety-critical domains.

---

### Step 4 — Engine Temperature Stress Test (Chaos / Resilience)

Injects 10 deliberate anomalies into 100 rows of telemetry (NaN, string values, physically impossible readings). Validates self-healing and graceful degradation.

```bash
PYTHONPATH="." python tools/stress_test_engine_temp.py
```

**What to observe:**
- Anomalies are detected and flagged without crashing the pipeline.
- Invalid rows are nullified and logged; valid rows pass through untouched.
- Pipeline resilience score is reported at the end.

---

### Step 5 — Tamper-Evident Audit Trail

Inspect the SHA-256 linked provenance chain produced by any run.

```bash
cat data/nhl_game_2024020001_audit.json | python -m json.tool | head -60
```

Or for a pipeline run with export:

```bash
PYTHONPATH="." python tools/demo_openf1.py --session 9158 --driver 1
cat data/openf1_audit.json | python -m json.tool
```

**What to observe:**
- Each record contains `input_hash`, `output_hash`, `previous_hash`, and `record_hash`.
- Hashes form a tamper-evident chain: altering any record breaks downstream hashes.
- Enables full reproducibility verification for peer review.

---

### Step 6 — HITL Retraining Loop (Active Learning)

Demonstrates the Human-in-the-Loop feedback pipeline. A reviewer corrects low-confidence mappings; the translator retrains incrementally.

```bash
PYTHONPATH="." python tools/demo_hitl_retraining.py
```

**What to observe:**
- Low-confidence resolutions are surfaced for human review.
- Accepted corrections are written to a feedback store and used to retrain the translator.
- Learning curves show confidence improving across iterations.
- This is the primary novel research contribution.

---

### Step 7 — Semantic Layer Benchmark

Quantitative evaluation of the BERT semantic reconciliation layer against a baseline (exact-match and edit-distance comparators).

```bash
PYTHONPATH="." python tools/benchmark_semantic_layer.py
```

**What to observe:**
- Precision, recall, and F1 reported for each domain (F1, NHL, Clinical).
- BERT cosine similarity outperforms baselines on ambiguous/abbreviated field names.
- Results written to `data/reports/` as PDF.

---

### Step 8 — PDF Audit Report

Generate a formatted PDF report for any pipeline run, suitable for submission or review.

```bash
PYTHONPATH="." python tools/demo_pdf_report.py
```

Output: `data/reports/demo_report.pdf`

---

### Full Showcase — Single Script

Run all stages in sequence:

```bash
source .venv/bin/activate

PYTHONPATH="." python tools/demo_openf1.py --session 9158 --driver 1
PYTHONPATH="." python tools/demo_nhl.py --game 2024020001
PYTHONPATH="." python main.py --adapter clinical --export-audit --audit-path data/clinical_audit.json
PYTHONPATH="." python tools/stress_test_engine_temp.py
PYTHONPATH="." python tools/demo_hitl_retraining.py
PYTHONPATH="." python tools/benchmark_semantic_layer.py
PYTHONPATH="." python tools/demo_pdf_report.py
```

Or run the same suite and auto-publish generated reports/CSVs:

```bash
source .venv/bin/activate
bash tools/run_showcase_and_publish.sh
```

---

## Research Contributions Summary

| Contribution | Demonstrated by |
|---|---|
| Autonomous schema drift resolution | Steps 1–3 |
| Domain-agnostic generalisation (F1, NHL, ICU) | Steps 1–3 |
| Chaos resilience without pipeline crash | Step 4 |
| Tamper-evident, reproducible audit trail | Step 5 |
| HITL active learning feedback loop | Step 6 |
| Quantitative benchmark vs. baselines | Step 7 |
| Structured reporting for peer review | Step 8 |

---

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

Optional:
- Docker (for containerised deployment)

## Configuration

- Audit logs: `data/reproducibility_audit.json`
- Provenance log: `data/provenance_log.jsonl`
- Reports: `data/reports/`

Environment variables are not required for core operation. External API calls rely on network access.

## Provenance and Auditability

Every semantic alignment writes a tamper-evident record (input hash → output hash) to `data/provenance_log.jsonl`. Audit logs can be exported from any adapter:

```python
adapter.export_audit_log("data/openf1_audit.json")
```

## HITL Analytics

```python
from modules.hitl_orchestrator import HumanInTheLoopOrchestrator

orchestrator = HumanInTheLoopOrchestrator()
orchestrator.display_feedback_summary()
```

## Testing

```bash
PYTHONPATH="." pytest tests/ -v
```

## Repository Structure

```
resilient-rap-framework/
├── modules/          # Core ingestion and semantic reconciliation
├── adapters/         # Domain adapters (OpenF1, NHL, Clinical, Sports)
├── tools/            # Demo and benchmark utilities
├── tests/            # Test suite (41 tests)
├── data/             # Audit logs, reports, synthetic data
├── reporting/        # PDF reporting
└── src/              # Provenance and analytics
```

## Licensing

This project is licensed under the PolyForm Noncommercial License 1.0.0. Commercial use requires a separate license.

Contact: tclarke91@proton.me

See LICENSE and CONTRIBUTING.md for details.

<img src="https://static.scarf.sh/a.png?x-pxid=a8f24add-7f46-4868-90bb-4c804a75e3fd&source=launch_Feb05" referrerpolicy="no-referrer-when-downgrade" />
