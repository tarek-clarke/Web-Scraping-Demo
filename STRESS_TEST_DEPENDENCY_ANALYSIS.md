# Stress Test Dependency Analysis
## Complete Dependency Tree for Three Stress Test Scripts

**Analysis Date:** February 26, 2026  
**Analyzed Scripts:**
1. `tools/System_gpu_stress_test.py`
2. `tools/System_stress_test.py`
3. `tools/stress_test_engine_temp.py`

---

## Dependency Trees

### 1. tools/System_gpu_stress_test.py

**Direct Dependencies (Local Modules):**
- `src/circuit_breaker.py` (TelemetryCircuitBreaker, TelemetryPacket, CircuitState)
- `src/local_persistence.py` (TracksideEdgeBuffer, BufferedPacket)
- `src/geo_fence.py` (GeoFence)
- `src/audit_log.py` (ComplianceAuditLog)
- `src/middleware/tracing.py` (RequestContext)
- `src/slo.py` (SLOTracker)

**Transitive Dependencies:**
- `src/geo_fence.py`  `src/audit_log.py` (already listed above)

**Total Unique Dependencies:** 6 files from src/

---

### 2. tools/System_stress_test.py

**Direct Dependencies (Local Modules):**
- `src/circuit_breaker.py` (TelemetryCircuitBreaker, TelemetryPacket, CircuitState)
- `src/local_persistence.py` (TracksideEdgeBuffer, BufferedPacket)
- `src/geo_fence.py` (GeoFence)
- `src/audit_log.py` (ComplianceAuditLog)
- `src/middleware/tracing.py` (RequestContext)
- `src/slo.py` (SLOTracker)

**Transitive Dependencies:**
- `src/geo_fence.py`  `src/audit_log.py` (already listed above)

**Total Unique Dependencies:** 6 files from src/

---

### 3. tools/stress_test_engine_temp.py

**Direct Dependencies (Local Modules):**
- `adapters/sports/ingestion_sports.py` (SportsIngestor)

**Transitive Dependencies:**
- None (SportsIngestor is a stub with no local imports)

**Total Unique Dependencies:** 1 file from adapters/

---

## Summary: Files USED by Stress Tests

### src/ directory (used by stress tests)
[x] **USED:**
- `src/circuit_breaker.py` (used by System_gpu_stress_test.py, System_stress_test.py)
- `src/local_persistence.py` (used by System_gpu_stress_test.py, System_stress_test.py)
- `src/geo_fence.py` (used by System_gpu_stress_test.py, System_stress_test.py)
- `src/audit_log.py` (used by System_gpu_stress_test.py, System_stress_test.py, and imported by geo_fence.py)
- `src/middleware/tracing.py` (used by System_gpu_stress_test.py, System_stress_test.py)
- `src/slo.py` (used by System_gpu_stress_test.py, System_stress_test.py)

### adapters/ directory (used by stress tests)
[x] **USED:**
- `adapters/sports/ingestion_sports.py` (used by stress_test_engine_temp.py)

### tools/ directory (the stress test scripts themselves)
[x] **STRESS TEST SCRIPTS:**
- `tools/System_gpu_stress_test.py` (stress test #1)
- `tools/System_stress_test.py` (stress test #2)
- `tools/stress_test_engine_temp.py` (stress test #3)

---

## Files NOT USED by Any Stress Test

### modules/ directory
[ ] **NOT USED (4 files):**
- `modules/base_ingestor.py`
- `modules/enhanced_translator.py`
- `modules/f1_telemetry_logger.py`
- `modules/translator.py`

### adapters/ directory
[ ] **NOT USED (2 files):**
- `adapters/openf1/__init__.py`
- `adapters/openf1/ingestion_openf1.py`

### benchmarks/ directory
[ ] **NOT USED (1 file):**
- `benchmarks/baselines.py`

### examples/ directory
[ ] **NOT USED (5 files):**
- `examples/debug_pipeline.py`
- `examples/demo_hitl_retraining.py`
- `examples/demo_openf1.py`
- `examples/demo_pdf_report.py`
- `examples/test_translator.py`

**Note:** `examples/stress_test_engine_temp.py` appears to be a duplicate/symlink of the stress test in tools/. Both are functionally identical.

### tools/ directory
[ ] **NOT USED (10 files, excluding the 3 stress tests):**
- `tools/__init__.py`
- `tools/benchmark_semantic_layer.py`
- `tools/generate_f1_telemetry.py`
- `tools/generate_semantic_benchmark_pdf.py`
- `tools/health_monitor.py`
- `tools/profile_embeddings.py`
- `tools/replay_stream.py`
- `tools/tui_replayer.py`
- `tools/validate_p99_latency.py`
- `tools/verify_amd_gpu.py`

### scripts/ directory
[ ] **NOT USED (1 file):**
- `scripts/update_docs.py`

### reporting/ directory
[ ] **NOT USED (1 file):**
- `reporting/pdf_report.py`

### experiments/ directory
[ ] **NOT USED (1 file):**
- `experiments/__init__.py`

### src/ directory (other files not used by stress tests)
[ ] **NOT USED (3 files):**
- `src/analytics/intervention_metrics.py`
- `src/middleware/__init__.py`
- `src/middleware/provenance.py`
- `src/provenance.py`

---

## Archival Recommendations

### Total Files to Archive: 28 files

**By Directory:**
- modules/: 4 files
- adapters/: 2 files
- benchmarks/: 1 file
- examples/: 5 files
- tools/: 10 files
- scripts/: 1 file
- reporting/: 1 file
- experiments/: 1 file
- src/analytics/: 1 file
- src/middleware/: 2 files

**Critical Dependencies to KEEP (9 files):**
1. `src/circuit_breaker.py`
2. `src/local_persistence.py`
3. `src/geo_fence.py`
4. `src/audit_log.py`
5. `src/middleware/tracing.py`
6. `src/slo.py`
7. `adapters/sports/ingestion_sports.py`
8. `tools/System_gpu_stress_test.py` (stress test)
9. `tools/System_stress_test.py` (stress test)
10. `tools/stress_test_engine_temp.py` (stress test)

---

## Dependency Graph Visualization

```
System_gpu_stress_test.py
 src/circuit_breaker.py (no local deps)
 src/local_persistence.py (no local deps)
 src/geo_fence.py
    src/audit_log.py (no local deps)
 src/audit_log.py (no local deps)
 src/middleware/tracing.py (no local deps)
 src/slo.py (no local deps)

System_stress_test.py
 src/circuit_breaker.py (no local deps)
 src/local_persistence.py (no local deps)
 src/geo_fence.py
    src/audit_log.py (no local deps)
 src/audit_log.py (no local deps)
 src/middleware/tracing.py (no local deps)
 src/slo.py (no local deps)

stress_test_engine_temp.py
 adapters/sports/ingestion_sports.py (no local deps)
```

---

## Notes

1. **Both System stress tests use identical dependencies** - they share the same 6 src/ files.

2. **The engine temp stress test is isolated** - it only uses a single adapter stub with no further dependencies.

3. **No circular dependencies detected** - the dependency tree is clean.

4. **src/geo_fence.py is the only file with a transitive dependency** - it imports src/audit_log.py, which is already directly imported by both System stress tests.

5. **All stress tests are self-contained** - they don't import from each other or from any of the files in modules/, benchmarks/, examples/, reporting/, or experiments/.

6. **The entire modules/ directory is unused** - all 4 files can be safely archived.

7. **Most of tools/ is unused** - 10 out of 13 files in tools/ are not dependencies of the stress tests (excluding the 3 stress test scripts themselves).
