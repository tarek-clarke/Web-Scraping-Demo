# Quick Start: Unified Pipeline

## One-Command Processing

Process all new raw results end-to-end:

```bash
python unified_pipeline.py
```

That's it! The script will:
1. ✓ Normalize hardware names and VRAM metadata
2. ✓ Merge all raw JSON files
3. ✓ Parse into empirical log with logic constraints
4. ✓ Generate final CSV for analysis

## Common Scenarios

### Scenario 1: Pull New Results and Process Everything
```bash
# Pull new raw results first
# (e.g., rsync or copy new JSON files to results/raw/)

# Then run full pipeline
python unified_pipeline.py
```

### Scenario 2: Reparse Without Re-merging
```bash
# Use this if you've already merged and want to update the empirical log only
python unified_pipeline.py --skip-merge
```

### Scenario 3: Merge Only (No Parsing)
```bash
# Use this to normalize and merge without generating the final empirical log
python unified_pipeline.py --skip-parse
```

## Outputs to Expect

After running the full pipeline:

```
✓ combined_results.json (24.7 MB) — Merged all results
✓ pristine_chaos_vs_repair_matrix.csv (2.6 MB) — Final empirical log
```

## Typical Workflow

```
1. Collect new raw evaluation results
   └─ Copy to results/raw/HARDWARE_NAME_GB/

2. Run unified pipeline
   └─ python unified_pipeline.py

3. Outputs ready for analysis
   └─ pristine_chaos_vs_repair_matrix.csv
   └─ Use for cross-platform comparison, charts, IEEE TKDE submission
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Merge fails | Check raw JSON format in results/raw/ |
| Parse fails | Try `--skip-merge` to test existing merged data |
| Want full logs | Pipeline prints detailed progress to console |

## Related Files

- `unified_pipeline.py` — Main orchestration script
- `merge_raw_results.py` — Phase 1: Normalization & merging
- `parse_raw_results.py` — Phase 2: Empirical log compilation
- `UNIFIED_PIPELINE_README.md` — Full documentation
- `EMPIRICAL_LOG_DOCUMENTATION.md` — Technical specification

---

**Status**: Production Ready  
**Version**: 1.0
