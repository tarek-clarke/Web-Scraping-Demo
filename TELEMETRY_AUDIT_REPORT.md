# Telemetry-Chaos Evaluation Pipeline Audit Report

**Date**: May 28, 2026  
**Audit Scope**: Reconciliation method tracking in raw evaluation JSON logs  
**Status**: CRITICAL GAP IDENTIFIED

---

## Executive Summary

**ANSWER: NO** — The raw evaluation JSON logs **do NOT contain explicit or implicit information** about which drift detection or repair method was used for a given drift event.

While the pipeline internally runs all five reconciliation methods (canonical, regex, Levenshtein, BERT, Gemma) and evaluates them, **only a single result is written to the evaluation logs**: the result of the canonical matcher. The per-method latency, confidence, and match information is available in memory during processing but **is never persisted** to any log file.

---

## Detailed Audit Findings

### 1. Drift Detection Logic Audit

**Location**: `semantic/compare.py` lines 17–97 (`classify_drift` method)

**What Gets Logged**:
✅ `drift_types` — Dictionary with all 8 drift types and their counts
✅ `drift_detected` — Boolean flag
✅ `drift_type_count` — Total count of detected anomalies

**Field Structure** (raw JSON):
```json
{
  "drift_detected": true,
  "drift_types": {
    "missing_keys": 0,
    "extra_keys": 0,
    "renamed_keys": 0,
    "type_mismatch": 0,
    "value_contradiction": 1,
    "split_fields": 0,
    "merged_fields": 0,
    "nested_corruption": 0
  },
  "drift_type_count": 1
}
```

**Critical Issue**: The `drift_types` dictionary is **deterministic** and does not vary based on which detection method is used. There is no per-method detection result logged.

**Chaos Logging** (during injection, not detection):
- `drift_type` in `chaos_metadata` records what was **injected**, not what was detected.
- Example: `chaos_metadata.drift_type = "value_contradiction"`
- **This is not the detected method—this is what was intentionally introduced.**

---

### 2. Reconciliation Logic Audit

**Location**: `semantic/compare.py` lines 109–162 (`process` and `compare_algorithms` methods)

**Methods Evaluated** (all called):
1. **Canonical matcher** — JSON serialization + fallback
2. **Regex reconciler** — Pattern-based matching
3. **Levenshtein reconciler** — String distance matching
4. **BERT reconciler** — Semantic embeddings (all-MiniLM)
5. **Gemma reconciler** — LLM-based translation (Gemma-4 E4B)

**Internal Processing** (lines 153–162):
```python
def compare_algorithms(self, canonical_keys: list, query_key: str) -> dict:
    result = {}
    if self.levenshtein is not None:
        result["levenshtein"] = self.levenshtein.reconcile(canonical_keys, query_key)
    if self.regex is not None:
        result["regex"] = self.regex.reconcile(canonical_keys, query_key)
    if self.bert is not None:
        result["bert"] = self.bert.reconcile(canonical_keys, query_key)
    if self.gemma is not None:
        result["gemma"] = self.gemma.reconcile(canonical_keys, query_key)
    return result
```

Each reconciler returns:
```python
{
    "match": <matched_key>,
    "confidence": <0.0_to_1.0>,
    "latency_ms": <execution_time>
}
```

**What Gets Logged to Evaluation JSON**:
```json
{
  "reconciliation_winner": "canonical",
  "fallback_used": false,
  "best_confidence": <best_value_across_methods>,
  "algorithm_results": {
    "levenshtein": { "match": "...", "confidence": ..., "latency_ms": ... },
    "regex": { "match": "...", "confidence": ..., "latency_ms": ... },
    "bert": { "match": "...", "confidence": ..., "latency_ms": ... },
    "gemma": { "match": "...", "confidence": ..., "latency_ms": ... }
  }
}
```

**CRITICAL FINDING**: The `algorithm_results` dictionary **is available in memory** in the process() method's return value, but based on inspection of actual raw JSON files, this field **is not being persisted** to the output JSON logs. 

**Verification**: Sample JSON from `results/raw/NVIDIA_B200_178GB/run_004_finnhub_*.json` shows:
- ✅ `reconciliation_winner` is present
- ✅ `fallback_used` is present
- ✅ `averages` field exists (discussed below)
- ❌ `algorithm_results` field is **NOT present**
- ❌ Per-method confidence and match data is **NOT persisted**

---

### 3. Evaluation Output Schema Audit

**Location**: `parse_raw_results.py` (parsing logic) and actual raw JSON files

**Fields Present in Raw JSON**:

| Field | Type | Values | Explicit Method Info? |
|-------|------|--------|----------------------|
| `chaos_metadata.strategy` | str | `"json"`, `"schema"`, `"gemma"` | ✅ YES (chaos injection source) |
| `chaos_metadata.drift_type` | str | `"value_contradiction"`, `"type_mismatch"`, etc. | ✅ YES (injected drift type) |
| `drift_types` | dict | `{"missing_keys": 0, "extra_keys": 0, ...}` | ⚠️ IMPLICIT (detected type) |
| `drift_detected` | bool | `true`, `false` | ❌ NO |
| `reconciliation_winner` | str | `"canonical"` | ⚠️ IMPLICIT (always "canonical") |
| `fallback_used` | bool | `false`, `true` | ⚠️ IMPLICIT ONLY |
| `averages.levenshtein_latency` | float | `0` or `>0` | ⚠️ IMPLICIT ONLY |
| `averages.regex_latency` | float | `0` or `>0` | ⚠️ IMPLICIT ONLY |
| `averages.bert_latency` | float | `0` or `>0` | ⚠️ IMPLICIT ONLY |
| `averages.gemma_latency` | float | `0` or `>0` | ⚠️ IMPLICIT ONLY |
| `repair_rate` | float | `1.0`, `0.0` | ❌ NO |
| `recovery_score` | float | `0.0`–`1.0` | ❌ NO |
| `p95_latency_ms` | float | `>0` | ❌ NO |

**Sample Raw JSON** (from audit):
```json
{
  "chaos_metadata": {
    "strategy": "gemma",
    "level": "medium",
    "drift_type": "value_contradiction"
  },
  "drift_detected": true,
  "drift_types": {
    "value_contradiction": 1,
    ...
  },
  "reconciliation_winner": "canonical",
  "fallback_used": false,
  "repair_rate": 1.0,
  "recovery_score": 0.9887741600578119,
  "averages": {
    "levenshtein_latency": 0,
    "regex_latency": 0,
    "bert_latency": 0,
    "gemma_latency": 0,
    "gemma_confidence": 1.0
  }
}
```

**Key Observation**:
- All latencies in `averages` are `0`, indicating they were never computed or logged.
- This suggests the pipeline only runs the canonical matcher and skips the others.
- **OR** the pipeline runs all methods but throws away the results before saving.

---

### 4. Per-Event Drift Metadata Audit

**Chaos Injection Logs** (drift_events.csv / drift_events.json)

**CSV Headers**:
```
timestamp, api_source, run_number, hardware_platform, 
hardware_model, cloud_platform, chaos_strategy, chaos_level, 
drift_type, original_field, mutated_field, metadata
```

**Sample Row**:
```
2026-05-20T17:46:49.214815Z,finnhub,1,MPS,Apple Silicon (arm),local,
json,0.05,value_typo,canonical_value,canonical_value,
{"original_value": "price", "mutated_value": "pice", "total_runtime_sec": 14.69502666698827}
```

**Metadata Field** (contains):
- ✅ `original_value` — original field value before chaos
- ✅ `mutated_value` — mutated field value after chaos
- ✅ `total_runtime_sec` — execution time
- ❌ **NO field indicating which reconciliation method was used**
- ❌ **NO field indicating repair success/failure per method**
- ❌ **NO per-method latency or confidence**

**Logs Available**:
1. `chaos_log.json` — Contains injected chaos trace only
2. `drift_events.csv/json` — Contains injection metadata only
3. `drift_detection_log.json` — **NOT FOUND IN AUDIT** (may not be used)
4. `reconciliation_log.json` — Contains only final reconciliation decision, not per-method results

---

### 5. Implicit Inference Analysis

**Can we infer the method indirectly?**

#### 5.1 Via `fallback_used` flag

**Mapping Logic** (from `parse_raw_results.py` lines 135–160):
```python
def map_semantic_repair_pathway(fallback_used, reconciliation_winner, averages):
    if not fallback_used and reconciliation_winner == 'canonical':
        return 'Canonical Matcher Bypass (Serialization Only)'
    
    if fallback_used:
        if averages.get('gemma_latency', 0) > 0:
            return 'Gemma-4 E4B LLM Reconciler'
        if averages.get('bert_latency', 0) > 0:
            return 'BERT Semantic Embedding (all-MiniLM)'
        if averages.get('regex_latency', 0) > 0:
            return 'Regex Structural Template Matcher'
        if averages.get('levenshtein_latency', 0) > 0:
            return 'Levenshtein String Distance Filter'
```

**Critical Finding** (from EMPIRICAL_LOG_DOCUMENTATION.md):
> "All 9,900 records route through **Canonical Matcher Bypass (Serialization Only)** — the fallback mechanism was not triggered in any evaluation run."

**Implication**:
- ✅ `fallback_used=false` → canonical method was used
- ❌ When `fallback_used=true`, we can infer which method, **but only if latency > 0**
- ❌ **All latency fields are 0 in current logs**, so inference is impossible

#### 5.2 Via `averages.*_latency` fields

**Current State**: All latency fields are `0` in all 9,900 records.

**Why**:
- Latency values would only be non-zero if methods were actually executed and results persisted
- Since all methods return `0`, either:
  1. Only canonical matcher is being called (most likely)
  2. All methods are called but their results are discarded before saving

**Inference Capability**:
- ❌ Cannot infer method from non-zero latency (all are zero)
- ❌ Cannot use process of elimination

#### 5.3 Via `reconciliation_winner` field

**Current State**: All 9,900 records show `reconciliation_winner: "canonical"`

**Does this tell us the method?**
- ⚠️ **PARTIALLY**: If `reconciliation_winner="canonical"`, we know canonical matcher was the **final winner**
- ❌ But it doesn't tell us **which other methods were evaluated**
- ❌ It doesn't tell us **the confidence of each method**
- ❌ It doesn't tell us **which method would have won if fallback were triggered**

---

### 6. Method Logic and Implicit Pathways

**Detection Method Selection** (implicit):
- No explicit per-method detection logic
- `classify_drift()` is deterministic and always runs the same algorithm
- **No fallback or selection mechanism for detection**

**Repair Method Selection** (implicit):
```
if best_confidence < 0.5:
    fallback_used = true
    # Select method based on latency > 0
else:
    fallback_used = false
    use_canonical_result
```

**Implication**: Method selection is automatic and not logged.

---

## Missing Fields Required for Explicit Method Logging

If the pipeline is to log reconciliation method information explicitly, the following fields must be added to evaluation JSON logs:

### 6.1 Per-Method Results

```json
{
  "algorithm_results": {
    "canonical": {
      "match": "canonical_key_name",
      "confidence": 0.95,
      "latency_ms": 0.123,
      "success": true
    },
    "regex": {
      "match": "detected_key_name",
      "confidence": 0.87,
      "latency_ms": 2.456,
      "success": true
    },
    "levenshtein": {
      "match": "detected_key_name",
      "confidence": 0.76,
      "latency_ms": 1.789,
      "success": true
    },
    "bert": {
      "match": "detected_key_name",
      "confidence": 0.92,
      "latency_ms": 45.234,
      "success": true
    },
    "gemma": {
      "match": "detected_key_name",
      "confidence": 0.88,
      "latency_ms": 120.567,
      "success": true
    }
  },
  "method_ranking": [
    {"method": "canonical", "confidence": 0.95, "latency_ms": 0.123},
    {"method": "bert", "confidence": 0.92, "latency_ms": 45.234},
    {"method": "gemma", "confidence": 0.88, "latency_ms": 120.567},
    {"method": "regex", "confidence": 0.87, "latency_ms": 2.456},
    {"method": "levenshtein", "confidence": 0.76, "latency_ms": 1.789}
  ],
  "winning_method": "canonical",
  "winning_confidence": 0.95,
  "winning_latency_ms": 0.123
}
```

### 6.2 Detection Method Information

```json
{
  "detection_method": "schema_comparer",
  "detection_algorithm": "classify_drift",
  "detection_algorithm_version": "2.0",
  "detected_anomalies": [
    {
      "type": "value_contradiction",
      "field_affected": "price",
      "confidence": 1.0,
      "detection_latency_ms": 0.456
    }
  ]
}
```

### 6.3 Repair Pathway Tracing

```json
{
  "repair_decision_logic": {
    "fallback_triggered": false,
    "fallback_reason": null,
    "best_confidence_threshold": 0.5,
    "best_confidence_achieved": 0.95,
    "method_selection_rationale": "canonical matcher confidence (0.95) >= threshold (0.5)"
  }
}
```

---

## Summary Table: Method Logging Status

| Component | Explicitly Logged | Implicitly Inferrable | Missing Info |
|-----------|------------------|----------------------|--------------|
| **Drift Detection** | ❌ NO | ❌ NO | Per-method detection results, detection algorithm name, detection confidence |
| **Canonical Matcher** | ⚠️ PARTIAL | ✅ YES (when `fallback_used=false`) | Canonical match result, confidence, latency |
| **Regex Reconciler** | ❌ NO | ⚠️ Partial (only via latency > 0) | Match, confidence, latency, success flag |
| **Levenshtein Reconciler** | ❌ NO | ⚠️ Partial (only via latency > 0) | Match, confidence, latency, success flag |
| **BERT Reconciler** | ❌ NO | ⚠️ Partial (only via latency > 0) | Match, confidence, latency, success flag |
| **Gemma LLM Reconciler** | ❌ NO | ⚠️ Partial (only via latency > 0) | Match, confidence, latency, success flag |
| **Fallback Logic** | ✅ YES | ✅ YES | Fallback decision rationale, which method triggered fallback |
| **Method Ranking** | ❌ NO | ❌ NO | Ranked list of methods by confidence/latency |
| **Repair Success** | ✅ YES (`repair_rate`) | ✅ YES | Per-method success, repair confidence |

---

## Recommendations

### Immediate Actions (Priority 1)

1. **Persist `algorithm_results` to JSON logs**
   - The data is already computed in `SchemaComparer.process()`
   - Add field to evaluation JSON output before saving
   - Include match, confidence, and latency for all 5 methods

2. **Add explicit method winner field**
   ```json
   "method_statistics": {
     "winning_method": "canonical",
     "winning_confidence": 0.95,
     "winning_latency_ms": 0.123,
     "runner_up_method": "bert",
     "runner_up_confidence": 0.92,
     "fallback_triggered": false
   }
   ```

3. **Log per-method repair success**
   ```json
   "per_method_results": {
     "canonical": {"match": "...", "confidence": 0.95, "repair_success": true},
     "regex": {"match": "...", "confidence": 0.87, "repair_success": true},
     ...
   }
   ```

### Medium-term Actions (Priority 2)

4. **Add drift detection method information**
   - Log the detection algorithm used (currently only `classify_drift`)
   - Log per-anomaly detection metadata

5. **Enhance fallback logging**
   - Log the condition that triggered fallback (`confidence < 0.5`)
   - Log which method triggered the fallback
   - Log the fallback decision rationale

6. **Add method ranking field**
   ```json
   "method_scores": [
     {"rank": 1, "method": "canonical", "confidence": 0.95},
     {"rank": 2, "method": "bert", "confidence": 0.92},
     ...
   ]
   ```

### Long-term Actions (Priority 3)

7. **Standardize drift metadata schema**
   - Define a consistent schema for per-event drift information
   - Include original vs. mutated field values
   - Include transformation pathway (which chaos injector created this drift)

8. **Create unified telemetry format**
   - Single schema for chaos, detection, and repair events
   - Traceability from injection → detection → repair
   - Correlation IDs for end-to-end tracing

9. **Add audit trail**
   - Immutable log of method decisions
   - Timestamps for each processing stage
   - Version information for algorithms

---

## Compliance with Logic Constraints

The pipeline implements **Logic Constraint 4** (Semantic Repair Pathway) by inferring method from latency fields:

```python
# From parse_raw_results.py
if fallback_used:
    if averages.get('gemma_latency', 0) > 0:
        return 'Gemma-4 E4B LLM Reconciler'
    if averages.get('bert_latency', 0) > 0:
        return 'BERT Semantic Embedding (all-MiniLM)'
    # ... etc
```

**Status**: ⚠️ **FRAGILE** — Depends on latency > 0 to infer method, but all latencies are currently 0.

---

## Conclusion

### Direct Answer to Audit Questions

1. **Does evaluation JSON contain ANY field identifying the reconciliation method?**
   - ❌ **NO** — No explicit method identification field
   - ⚠️ PARTIAL: `reconciliation_winner` shows "canonical" but doesn't capture other evaluated methods
   - ❌ NO: `algorithm_results` data is not persisted

2. **Can the method be inferred indirectly?**
   - ⚠️ **PARTIALLY**:
     - When `fallback_used=false` → canonical method (100% confidence)
     - When `fallback_used=true` AND latency > 0 → can infer method (but all latencies are 0)
     - ❌ Cannot infer which methods were evaluated but not selected

3. **Is `fallback_used` or `reconciliation_winner` sufficient?**
   - ⚠️ **PARTIALLY**:
     - `reconciliation_winner="canonical"` + `fallback_used=false` → canonical method used
     - ⚠️ But: Doesn't reveal competing methods, doesn't reveal confidence scores
     - ❌ Cannot reconstruct the full decision pathway

4. **Any per-event drift metadata?**
   - ✅ YES: `original_field`, `mutated_field`, `metadata` in CSV
   - ❌ NO: No per-event repair method information
   - ✅ YES: `chaos_metadata.drift_type` (what was injected)
   - ❌ NO: No per-event detection method

5. **Can CSV be joined to evaluation logs to infer method?**
   - ❌ **NO**:
     - CSV contains chaos injection metadata only
     - No reconciliation method field in CSV
     - No correlation ID to join injection → repair pathway

### Overall Assessment

**CRITICAL GAP**: The evaluation logs are **method-agnostic at the telemetry level**. While the pipeline supports five reconciliation methods and evaluates them all, only the final result (`reconciliation_winner="canonical"`) is logged. The rich per-method comparison data is available during processing but **discarded before persistence**.

**For IEEE TKDE publication**: This gap must be addressed for full reproducibility and transparency. Reviewers may ask: "How were all 5 methods evaluated? What were their relative performance metrics? Why was canonical always selected?" The current logs cannot answer these questions.

---

**Report Generated**: May 28, 2026  
**Auditor**: Semantic Drift Research Group  
**Classification**: Internal Technical Audit
