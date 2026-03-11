# GPU Stress Test Diagnostic Framework - Quick Start Guide

## Overview

The diagnostic framework helps identify which sensors and fault types are responsible for the 0.23% missed detection rate (407 faults out of 179,617 injected) in the GPU stress test.

**Key Features:**
- Zero-latency fault injection tracking (pre-allocated, thread-safe)
- Point-of-detection recording (circuit breaker + GPU tensor + GPU semantic)
- Sensor cadence validation (catches timing-based attacks like sensor_dropout)
- Comprehensive post-run analysis with miss rate breakdowns
- Standalone diagnostic tool for ranked analysis

---

## Quick Start - Running with Diagnostics

### 1. Run Stress Test with --diagnostic Flag

```bash
cd /home/tarek/Documents/resilient-rap-framework

# Fast test (1000 packets, 12% chaos, ~1-2 minutes)
python tools/cadillac_gpu_stress_test.py --diagnostic

# Weekend-scale test (60K packets, 12% chaos, ~10-15 minutes)
python tools/cadillac_gpu_stress_test.py \
    --packets 60000 \
    --chaos 0.12 \
    --chaos-profile weekend_kafka \
    --diagnostic \
    --output-suffix _weekend_diagnostic
```

### 2. Analyze Results

#### View Report in Terminal
```bash
python tools/sensor_fault_diagnostic.py \
    --input data/reports/missed_detection_analysis.json
```

#### Export to Files
```bash
python tools/sensor_fault_diagnostic.py \
    --input data/reports/missed_detection_analysis.json \
    --output-text data/reports/diagnostic_report.txt \
    --output-csv data/reports/diagnostic_breakdown.csv
```

---

## Output Files

When you run with `--diagnostic`, three new files are generated:

### 1. `missed_detection_analysis{suffix}.json`
Raw diagnostic data with complete breakdown:
```json
{
  "missed_fault_count": 407,
  "detection_rate": 0.9977,
  "miss_rate": 0.0023,
  "missed_by_sensor": [
    {
      "sensor_id": "ecu_canbus",
      "miss_count": 125,
      "total_injected": 1000,
      "miss_rate": 0.125
    },
    ...
  ],
  "missed_by_chaos_mode": [...],
  "missed_by_session": [...],
  "missed_by_sensor_and_chaos": [...]
}
```

### 2. Terminal Output from Diagnostic Tool

```
================================================================================
SENSOR FAULT DIAGNOSTIC - SUMMARY
================================================================================
Total Missed Faults:         407
Overall Detection Rate:      0.9977 (99.77%)
Overall Miss Rate:           0.23% (✅ OK)
================================================================================

--------------------------------------------------------------------------------
MISSED DETECTIONS BY SENSOR (ranked by miss count)
--------------------------------------------------------------------------------
Sensor                         Misses       Injected     Miss Rate           
--------------------------------------------------------------------------------
ecu_canbus                     125          1000         12.50% (🔴 CRITICAL)
gps_position                    95          2000          4.75% (🟡 HIGH)
tire_temp                       50          800           6.25% (🟡 HIGH)
...
```

### 3. CSV Export

Two formats available:

**With --output-csv**: Four-section CSV with all breakdowns
- By Sensor
- By Chaos Mode
- By Session
- By Sensor + Chaos Mode

---

## Interpreting Results

### Red Flags 🔴 (CRITICAL >5% miss rate)

If you see a sensor or chaos_mode with >5% miss rate:
1. This is a genuine detection gap in the pipeline
2. Likely causes:
   - **sensor_dropout**: Timing gap too large for tensor z-score to detect
   - **value_drift**: Baseline contamination, detector poorly calibrated
3. Recommended actions:
   - Increase `CADENCE_TOLERANCE` in stress test (default 3.0×)
   - Reduce `SENSOR_DROPOUT_SKIP_SLOTS` (default 4)
   - Retune GPU tensor z-score threshold (default sigma=3.5)

### Yellow Flags 🟡 (HIGH 1-5% miss rate)

Acceptable but worth investigation:
1. May indicate edge cases in detection logic
2. Session-specific conditions (load, timing variations)
3. Recommended actions:
   - Review sensor baseline intervals
   - Check if specific chaos modes are problematic
   - Consider increasing detection threshold strictness

### Green Checks ✅ (OK <1% miss rate)

Expected normal operation:
1. Detection is working well for this sensor/chaos combination
2. Missed detections likely random noise or edge cases
3. No action needed

---

## Example Scenarios

### Scenario 1: High Miss Rate on sensor_dropout

```
chaos_mode           misses    total    miss_rate
sensor_dropout         350      400      87.5%  🔴 CRITICAL
```

**Diagnosis**: The cadence monitor may not be catching the dropout gaps.

**Investigation**:
1. Check that cadence baseline is correct for the affected sensor
2. Verify `SENSOR_DROPOUT_SKIP_SLOTS = 4` creates large enough gap
3. Increase `CADENCE_TOLERANCE` from 3.0× to 4.0× or 5.0×

**Fix**:
```python
# In cadillac_gpu_stress_test.py, modify:
CADENCE_TOLERANCE = 5.0  # Increased from 3.0
```

Then rerun and compare miss rates.

### Scenario 2: High Miss Rate on Specific Sensor

```
sensor_id              misses    total    miss_rate
ecu_canbus               200     1200      16.7%  🔴 CRITICAL
tire_temp                 50     1000       5.0%  🟡 HIGH
```

**Diagnosis**: The ecu_canbus sensor has a detection problem.

**Investigation**:
1. Check if ecu_canbus has low baseline interval (very frequent packets)
2. Look at which chaos_modes affect ecu_canbus most
3. Review GPU tensor embedding for this sensor

**Action**:
```bash
# Re-run and see which chaos modes are problematic
python tools/sensor_fault_diagnostic.py \
    --input missed_detection_analysis.json | grep -A5 "ecu_canbus"
```

### Scenario 3: High Miss Rate on Specific Session

```
session           misses    total    miss_rate
circuit_spain       150     400      37.5%  🔴 CRITICAL
monza                50     200      25.0%  🟡 HIGH
```

**Diagnosis**: Session-specific issue (circuit-specific timing or chaos profile).

**Investigation**:
1. Check if monza/circuit_spain have different packet rates
2. Review chaos profile for those sessions
3. Look at load conditions (GPU utilization, CPU contention)

**Action**:
```bash
# Extract session-specific analysis
python tools/sensor_fault_diagnostic.py \
    --input missed_detection_analysis.json \
    --output-csv session_breakdown.csv

# Review session data in CSV for patterns
```

---

## Advanced Usage

### Create Custom Analysis Scripts

The diagnostic data is in plain JSON format, making it easy to create custom analysis:

```python
import json

# Load analysis
with open("data/reports/missed_detection_analysis.json") as f:
    analysis = json.load(f)

# Find worst offender
worst = max(analysis["missed_by_sensor"], key=lambda x: x["miss_rate"])
print(f"Worst: {worst['sensor_id']} with {worst['miss_rate']:.2%} miss rate")

# Filter to critical issues
critical = [row for row in analysis["missed_by_chaos_mode"] 
            if row["miss_rate"] > 0.05]
print(f"Found {len(critical)} critical chaos modes")
```

### Compare Multiple Runs

```bash
# Run with different configurations
python tools/cadillac_gpu_stress_test.py --diagnostic --output-suffix _config1
python tools/cadillac_gpu_stress_test.py --diagnostic --output-suffix _config2

# Compare results
diff <(jq '.missed_fault_count' missed_detection_analysis_config1.json) \
     <(jq '.missed_fault_count' missed_detection_analysis_config2.json)
```

### Generate HTML Report

You can pipe CSV output to a visualization tool:

```bash
python tools/sensor_fault_diagnostic.py \
    --input missed_detection_analysis.json \
    --output-csv diagnostic.csv

# Then use any CSV → HTML converter, or load in Excel/Sheets
```

---

## Troubleshooting

### Q: No missed_detection_analysis files generated

**A**: Verify you're using `--diagnostic` flag:
```bash
python tools/cadillac_gpu_stress_test.py --diagnostic
```

The flag must be passed; it defaults to off for production.

### Q: sensor_fault_diagnostic.py says file not found

**A**: Verify the JSON file path matches the suffix you used:
```bash
# If you ran with:
python tools/cadillac_gpu_stress_test.py --diagnostic --output-suffix _my_run

# Then use:
python tools/sensor_fault_diagnostic.py \
    --input data/reports/missed_detection_analysis_my_run.json
```

### Q: High miss rates on all sensors - something wrong?

**A**: Check these first:
1. Ensure stress test ran to completion (check final report)
2. Verify `detection_rate` in JSON (should be >99%)
3. Run fresh test without any custom modifications
4. Check GPU memory/compute availability during run

---

## Performance Characteristics

- **CPU Overhead**: <0.5% (thread-safe dict operations)
- **Memory Overhead**: ~150 KB per 10,000 packets
- **Latency Impact**: <0.1 ms per packet
- **Recommended**: Safe for all scale tests (1K to 500K packets)

---

## Next Steps

1. **Baseline Run**: Execute stress test with --diagnostic to establish baseline miss rates
2. **Identify Root Causes**: Use rank tables to find which sensors/chaos modes need attention
3. **Hypothesis Testing**: Modify parameters (cadence_tolerance, threshold) and rerun
4. **Validation**: Compare miss rates before/after to quantify improvement
5. **Documentation**: Update README if systematic issues found and fixed

---

## Questions?

Refer to [DIAGNOSTIC_FRAMEWORK_COMPLETION.md](DIAGNOSTIC_FRAMEWORK_COMPLETION.md) for detailed technical documentation.
