# Unified Results Processing Pipeline

## Overview

`unified_pipeline.py` orchestrates a complete end-to-end workflow that processes raw evaluation results:

1. **Phase 1: Merge & Normalize** — Runs `merge_raw_results.py`
   - Normalizes hardware folder names with VRAM metadata
   - Merges all raw JSON files into unified outputs
   - Generates `combined_results.json` and hardware-specific aggregates

2. **Phase 2: Parse & Compile** — Runs `parse_raw_results.py`
   - Parses individual raw JSON files with logic constraints
   - Maps Chaos Source, Injected/Detected Types, Repair Pathway
   - Compiles unified empirical log: `pristine_chaos_vs_repair_matrix.csv`

3. **Phase 3: Event-Level Traceability** (optional) — `--with-traceability`
   - Links evaluation runs with drift events by `run_id`
   - Attaches `chaos_events` and `chaos_event_count` to each run
   - Reports orphan events and missing metadata

---

## One-Shot Copy-Paste Pipeline

Copy-paste the entire block below onto a **fresh cloud instance** (vast.ai, runpod, Lambda, etc.):

```bash
# ═══════════════════════════════════════════════════════════════════════════════
# ONE-SHOT SETUP:  Clone → Bootstrap → Run Evaluation → Push Results
# ═══════════════════════════════════════════════════════════════════════════════

# 1. Clone the repository
git clone https://github.com/YOUR_ORG/resilient-rap-framework.git
cd resilient-rap-framework

# 2. Create and activate a Python virtual environment
python3.10 -m venv .venv
source .venv/bin/activate

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install project dependencies (auto-detects CUDA / ROCm / MPS / CPU)
pip install -r requirements.txt

# 5. Bootstrap: installs the correct PyTorch wheel, caches MiniLM & Gemma
#    weights, and builds the C++ acceleration layer. Run once per machine.
python bootstrap.py --bootstrap

# 6. Run the full evaluation pipeline
#    --generate-only      write raw JSON artifacts (recommended for first run)
#    --require-gpu        abort if no GPU found
#    --strict-mode        abort on any fallback or missing model
#    --runs-per-config 5  runs per configuration
#    --policy-tag         tag embedded in every record for provenance
python run_all.py --generate-only --require-gpu --strict-mode --runs-per-config 5 --policy-tag tkde_policy_v1

# 7. Archive old results first (if any exist), then process new results
python unified_pipeline.py --with-traceability

# 8. (Optional) Push results to GitHub
git add results/ logs/ combined_results.* pristine_chaos_vs_repair_matrix.csv
git commit -m "results: $(hostname) $(date +%Y-%m-%d)"
git push origin main
```

### Quick Variants

| Scenario | Command |
|----------|---------|
| **GPU required, strict mode** | `python run_all.py --require-gpu --strict-mode` |
| **CPU fallback allowed** | `python run_all.py --no-require-gpu --cpu-allowed` |
| **Full benchmark (all phases + ablations)** | `python run_all.py --runs-per-config 4` |
| **Overnight headless run** | `python run_overnight.py` |
| **Run if already bootstrapped** | `python run_all.py` |

---

## Usage

### Full Pipeline (Merge + Parse)
```bash
python unified_pipeline.py
```

### Parse Only (Skip Merge)
```bash
python unified_pipeline.py --skip-merge
```

### Merge Only (Skip Parse)
```bash
python unified_pipeline.py --skip-parse
```

### With Event-Level Traceability
```bash
python unified_pipeline.py --with-traceability
```

---

## Workflow

### Typical Scenario: Pull New Results

1. New raw results are added to `results/raw/` (in hardware-named subdirectories)
2. Run: `python unified_pipeline.py --with-traceability`
3. Pipeline automatically:
   - ✓ Normalizes hardware naming and VRAM metadata
   - ✓ Merges all JSON files into `combined_results.json`
   - ✓ Generates per-hardware aggregates
   - ✓ Parses raw JSON with all logic constraints
   - ✓ Links evaluation runs ↔ drift events by `run_id`
   - ✓ Exports final empirical log: `pristine_chaos_vs_repair_matrix.csv`

---

## Pre-Flight Validation

Before ANY run begins, `run_all.py` performs strict validation:

| Check | Abort Condition |
|-------|----------------|
| GPU availability | `require_gpu=True` + no GPU → ABORT (unless `cpu_allowed=True`) |
| Hardware backend | Tensor placement test fails → ABORT (in strict mode) |
| BERT availability | `require_local_models=True` + BERT not local → ABORT |
| Gemma availability | `require_local_models=True` + Gemma not local → ABORT |
| Internet handshake | Any model loaded from internet → logged |
| Strict mode | Any fallback / missing model / unexpected internet → ABORT |

Pre-flight results are embedded in every evaluation record as `preflight` and in the summary JSON.

---

## Event-Level Traceability

Each run and chaos event is assigned a unique UUID:

- **`run_id`**: Generated at the start of every stream in `run_all.py`
- **`event_id`**: Generated for every chaos mutation in the chaos generators

These IDs are persisted in:
- Evaluation JSON records
- `drift_events.csv` / `drift_events.json`
- Linked traceability output (`results/global_traceability_linked.json`)

Explicit method logging records which reconciler won (`method_used`) and full per-algorithm results (`algorithm_results`) including confidence, latency, and match.

---

## Outputs

| File | Purpose |
|------|---------|
| `combined_results.json` | Unified merged results (all records) |
| `combined_results.csv` | CSV version of merged results |
| `pristine_chaos_vs_repair_matrix.csv` | Final empirical log (24 columns) |
| `hardware_results/*.json` | Per-hardware aggregates |
| `results/global_traceability_linked.json` | Event-linked records with `chaos_event_count` |
| `results/raw/<hardware>/run_*.json` | Per-run raw evaluation artifacts |

---

## Command-Line Options

```
--skip-merge           Skip Phase 1 (Merge)
--skip-parse           Skip Phase 2 (Parse)
--with-traceability    Run event-level traceability linking
--help, -h             Show usage documentation
```

---

## Error Handling

- **Merge failure**: Pipeline halts — use `--skip-merge` to proceed
- **Parse failure**: Check for corrupted JSON files in `results/raw/`
- **Pre-flight failure**: Pipeline aborts — check GPU/model availability
- **Traceability warnings**: Orphan events or runs with zero chaos events reported

---

## Example Output Log

```
2026-05-28 14:32:33 | PHASE 1: Merge & Normalize Raw Results
2026-05-28 14:32:40 | ✓ Merge phase completed successfully
2026-05-28 14:32:40 | PHASE 2: Parse & Compile Empirical Log
2026-05-28 14:32:45 | ✓ Parse phase completed successfully
2026-05-28 14:32:46 | PHASE 3: Event-Level Traceability Linking
2026-05-28 14:32:46 |   Runs processed      : 864
2026-05-28 14:32:46 |   Events linked       : 864
2026-05-28 14:32:46 |   Orphan events       : 0
2026-05-28 14:32:46 | PIPELINE SUMMARY
2026-05-28 14:32:46 | Phase 1 (Merge):              ✓ SUCCESS
2026-05-28 14:32:46 | Phase 2 (Parse):              ✓ SUCCESS
2026-05-28 14:32:46 | Phase 3 (Traceability):       ✓ COMPLETE
```

---

## Requirements

- Python 3.10+
- pandas, numpy
- PyTorch (installed by `bootstrap.py` with hardware-appropriate wheel)
- sentence-transformers, transformers, accelerate

---

## See Also

- [parse_raw_results.py](parse_raw_results.py) — IEEE TKDE empirical log compiler
- [merge_raw_results.py](merge_raw_results.py) — Raw results normalization
- [EMPIRICAL_LOG_DOCUMENTATION.md](EMPIRICAL_LOG_DOCUMENTATION.md) — Tech spec
- [bootstrap.py](bootstrap.py) — Environment initialization
- [run_all.py](run_all.py) — Evaluation runner with pre-flight checks
- [run_overnight.py](run_overnight.py) — Headless overnight pipeline

---

**Version**: 2.0  
**Date**: May 28, 2026  
**Author**: Semantic Drift Research Group
