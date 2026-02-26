# Archive Summary

This document tracks files that were moved to the `archive/` folder because they are not used by the stress test scripts referenced in the README.

## Stress Test Scripts (Active)

The following stress test scripts remain active:
- `tools/cadillac_gpu_stress_test.py` - GPU-accelerated stress test
- `tools/cadillac_stress_test.py` - CPU stress test  
- `tools/stress_test_engine_temp.py` - Engine temperature stress test

## Dependencies Used by Stress Tests

The stress tests use only these modules from the codebase:

### From `src/`:
- `circuit_breaker.py` - TelemetryCircuitBreaker, TelemetryPacket, CircuitState
- `local_persistence.py` - TracksideEdgeBuffer, BufferedPacket
- `geo_fence.py` - GeoFence
- `audit_log.py` - ComplianceAuditLog
- `middleware/tracing.py` - RequestContext
- `slo.py` - SLOTracker

### From `adapters/`:
- `sports/ingestion_sports.py` - SportsIngestor (used by stress_test_engine_temp.py)

### From `tests/`:
- `chaos_engine.py` - Used by test_cadillac_modules.py
- `test_cadillac_modules.py` - Tests for stress test modules
- `test_engine_temp_stress.py` - Tests for engine temp stress

## Archived Files (36 files)

Files moved to `archive/` with original folder structure maintained:

### modules/ (4 files) - 100% archived
- `base_ingestor.py`
- `enhanced_translator.py`
- `f1_telemetry_logger.py`
- `translator.py`

### adapters/ (2 files)
- `openf1/__init__.py`
- `openf1/ingestion_openf1.py`

### benchmarks/ (1 file) - 100% archived
- `baselines.py`

### examples/ (9 files) - 100% archived
- `debug_pipeline.py`
- `demo_hitl_retraining.py`
- `demo_openf1.py`
- `demo_pdf_report.py`
- `stress_test_engine_temp.py` (duplicate of tools/ version)
- `test_translator.py`
- `SEMANTIC_MATCH_REVIEW_CARD.md`
- `SemanticMatchReviewCard.examples.tsx`
- `SemanticMatchReviewCard.tsx`

### tools/ (11 files)
- `benchmark_semantic_layer.py`
- `generate_f1_telemetry.py`
- `generate_semantic_benchmark_pdf.py`
- `health_monitor.py`
- `profile_embeddings.py`
- `replay_stream.py`
- `run_cadillac_showcase.sh`
- `run_showcase_and_publish.sh`
- `tui_replayer.py`
- `validate_p99_latency.py`
- `verify_amd_gpu.py`

### scripts/ (1 file) - 100% archived
- `update_docs.py`

### reporting/ (1 file) - 100% archived
- `pdf_report.py`

### experiments/ (1 file) - 100% archived
- `__init__.py`

### src/ (3 files)
- `provenance.py`
- `middleware/provenance.py`
- `analytics/intervention_metrics.py`

### tests/ (3 files)
- `drift_simulator.py`
- `test_pdf_report.py`
- `tui_replayer_tests.csv`

### data/generators/ (1 file) - 100% archived
- `__init__.py`

## Active Files Remaining

### Active Production Code:
- **tools/** (3 stress test scripts + __init__.py)
- **src/** (6 core modules used by stress tests)
- **adapters/sports/** (1 adapter used by stress tests)
- **tests/** (3 test files for stress tests)

### Empty Directories (ready for new files):
- modules/
- benchmarks/
- examples/
- scripts/
- reporting/
- experiments/

## Archive Location

All archived files maintain their original folder structure inside:
```
archive/
├── adapters/
├── benchmarks/
├── data/
├── examples/
├── experiments/
├── modules/
├── reporting/
├── scripts/
├── src/
├── tests/
└── tools/
```

## Restoration

To restore an archived file, use git mv:
```bash
git mv archive/path/to/file.py original/path/to/file.py
```

---
*Generated: 2026-02-26*
*Based on: README.md stress test dependencies*
