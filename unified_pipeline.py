#!/usr/bin/env python3
"""
Unified Results Processing Pipeline
=====================================

Orchestrates the complete results processing workflow:
1. Normalize and merge raw results (merge_raw_results.py)
2. Parse merged results into empirical log (parse_raw_results.py)
3. Link evaluation results with drift events for full event-level traceability

This script allows you to pull new raw results and process them 
end-to-end in a single command.

Usage:
    python unified_pipeline.py [--skip-merge] [--skip-parse] [--with-traceability]

Options:
    --skip-merge         Skip the merge phase, go directly to parsing
    --skip-parse         Skip the parse phase, only run merge
    --with-traceability  Run event-level traceability linking after parse
    --help               Show this message

Author: Semantic Drift Research Group
Date: May 2026
"""

import sys
import os
import json
import csv
import logging
import subprocess
from pathlib import Path
from uuid import uuid4
from collections import defaultdict

# ============================================================================
# Configuration & Logging
# ============================================================================

LOG_LEVEL = logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent.absolute()
MERGE_SCRIPT = SCRIPT_DIR / 'merge_raw_results.py'
PARSE_SCRIPT = SCRIPT_DIR / 'parse_raw_results.py'

RESULTS_DIR = SCRIPT_DIR / 'results'
LOGS_DIR = SCRIPT_DIR / 'logs'
COMBINED_RESULTS_JSON = SCRIPT_DIR / 'combined_results.json'
DRIFT_EVENTS_CSV = SCRIPT_DIR / 'logs' / 'drift_events.csv'
DRIFT_EVENTS_JSON = SCRIPT_DIR / 'logs' / 'drift_events.json'


# ============================================================================
# Event-Level Traceability
# ============================================================================

def link_events_by_run_id():
    """
    Join evaluation JSONs ↔ drift_events.csv using run_id.

    For each evaluation run:
    - Find matching chaos events by run_id
    - Attach chaos_events list
    - Count chaos_event_count
    - Propagate method_used, algorithm_results, internet_used, model_source,
      model_version, hardware_backend_verified, pipeline_version

    Returns:
        dict: Summary of linking statistics
    """
    logger.info("=" * 80)
    logger.info("TRACEABILITY: Linking Evaluation Runs ↔ Drift Events")
    logger.info("=" * 80)

    # ── Load all evaluation records ──
    eval_records = []
    if COMBINED_RESULTS_JSON.exists():
        try:
            with open(COMBINED_RESULTS_JSON, 'r') as f:
                combined = json.load(f)
                if isinstance(combined, list):
                    eval_records = combined
                elif isinstance(combined, dict):
                    eval_records = [combined]
            logger.info(f"Loaded {len(eval_records)} evaluation records from {COMBINED_RESULTS_JSON.name}")
        except Exception as e:
            logger.error(f"Failed to load combined results: {e}")
            return None

    # Also search per-platform master JSON files
    platform_records = []
    if RESULTS_DIR.exists():
        for hw_dir in sorted(RESULTS_DIR.iterdir()):
            if hw_dir.is_dir():
                master_json = hw_dir / 'master_platform_all_runs_1_to_4.json'
                if master_json.exists():
                    try:
                        with open(master_json, 'r') as f:
                            records = json.load(f)
                            if isinstance(records, list):
                                platform_records.extend(records)
                                logger.info(f"  Loaded {len(records)} records from {master_json}")
                    except Exception as e:
                        logger.warning(f"  Failed to load {master_json}: {e}")

    if not eval_records and not platform_records:
        logger.warning("No evaluation records found — try running merge phase first.")
        return None

    all_records = eval_records + platform_records
    # Deduplicate by run_id
    seen_run_ids = set()
    unique_records = []
    for r in all_records:
        rid = r.get('run_id') or r.get('run_id', '')
        if rid and rid not in seen_run_ids:
            seen_run_ids.add(rid)
            unique_records.append(r)
        elif not rid:
            unique_records.append(r)

    logger.info(f"Total unique evaluation records: {len(unique_records)}")

    # ── Load drift events ──
    drift_events = []
    if DRIFT_EVENTS_JSON.exists():
        try:
            with open(DRIFT_EVENTS_JSON, 'r') as f:
                drift_events = json.load(f)
            logger.info(f"Loaded {len(drift_events)} drift events from {DRIFT_EVENTS_JSON.name}")
        except Exception as e:
            logger.error(f"Failed to load drift events JSON: {e}")

    # Also try CSV
    csv_events = []
    if DRIFT_EVENTS_CSV.exists():
        try:
            with open(DRIFT_EVENTS_CSV, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    csv_events.append(row)
            logger.info(f"Loaded {len(csv_events)} drift events from {DRIFT_EVENTS_CSV.name}")
        except Exception as e:
            logger.error(f"Failed to load drift events CSV: {e}")

    # ── Index drift events by run_id ──
    events_by_run_id = defaultdict(list)
    for ev in drift_events:
        rid = ev.get('run_id', '')
        if rid:
            events_by_run_id[rid].append(ev)

    # Also index CSV events
    csv_events_by_run_id = defaultdict(list)
    for ev in csv_events:
        rid = ev.get('run_id', '')
        if rid:
            csv_events_by_run_id[rid].append(ev)

    # ── Link events to evaluation records ──
    linked_count = 0
    orphan_event_run_ids = set()
    matched_run_ids = set()

    for rec in unique_records:
        rid = rec.get('run_id', '')
        if not rid:
            continue

        matched_run_ids.add(rid)

        # Find matching chaos events
        chaos_events = events_by_run_id.get(rid, [])
        if not chaos_events:
            chaos_events = csv_events_by_run_id.get(rid, [])

        chaos_event_count = len(chaos_events)

        # Attach to record
        rec['chaos_event_count'] = chaos_event_count
        rec['chaos_events'] = chaos_events

        # Propagate traceability fields from first chaos event if available
        if chaos_events:
            first_ev = chaos_events[0]
            rec['event_id'] = first_ev.get('event_id', rec.get('event_id', ''))
            rec['drift_metadata'] = first_ev.get('drift_metadata', first_ev.get('metadata', {}))

        linked_count += 1

        if chaos_event_count == 0:
            logger.warning(f"  [WARN] Evaluation run {rid[:12]} has ZERO matching chaos events")

    # ── Detect orphan events (events with no matching evaluation run) ──
    all_event_run_ids = set(events_by_run_id.keys()) | set(csv_events_by_run_id.keys())
    orphan_event_run_ids = all_event_run_ids - matched_run_ids

    orphan_events_count = 0
    for oid in orphan_event_run_ids:
        orphan_events_count += len(events_by_run_id.get(oid, []))
        orphan_events_count += len(csv_events_by_run_id.get(oid, []))

    # ── Build summary ──
    summary = {
        "evaluation_runs_processed": len(unique_records),
        "evaluation_runs_linked": linked_count,
        "chaos_events_total": len(drift_events) + len(csv_events),
        "chaos_events_linked": sum(
            len(events_by_run_id.get(rid, [])) + len(csv_events_by_run_id.get(rid, []))
            for rid in matched_run_ids
        ),
        "orphan_event_run_ids": len(orphan_event_run_ids),
        "orphan_events_count": orphan_events_count,
        "missing_event_runs": sum(
            1 for r in unique_records if r.get('chaos_event_count', 0) == 0
        ),
    }

    logger.info(f"\n  Runs processed      : {summary['evaluation_runs_processed']}")
    logger.info(f"  Runs linked         : {summary['evaluation_runs_linked']}")
    logger.info(f"  Events total        : {summary['chaos_events_total']}")
    logger.info(f"  Events linked       : {summary['chaos_events_linked']}")
    logger.info(f"  Orphan event run IDs: {summary['orphan_event_run_ids']}")
    logger.info(f"  Orphan events       : {summary['orphan_events_count']}")
    logger.info(f"  Runs w/o events     : {summary['missing_event_runs']}")

    if summary['orphan_event_run_ids'] > 0:
        logger.warning(f"  [WARN] {summary['orphan_event_run_ids']} orphan event run IDs "
                       f"({summary['orphan_events_count']} events) with no matching evaluation run")

    if summary['missing_event_runs'] > 0:
        logger.warning(f"  [WARN] {summary['missing_event_runs']} evaluation runs have zero chaos events")

    # ── Write traceability-augmented output ──
    trace_output = SCRIPT_DIR / 'results' / 'global_traceability_linked.json'
    os.makedirs(trace_output.parent, exist_ok=True)
    with open(trace_output, 'w') as f:
        json.dump({
            "summary": summary,
            "linked_records": unique_records,
            "orphan_event_run_ids": list(orphan_event_run_ids),
        }, f, indent=2)
    logger.info(f"  Written traceability-augmented data to {trace_output.name}")

    logger.info("=" * 80)
    return summary


# ============================================================================
# Pipeline Orchestration (existing)
# ============================================================================

def run_merge_phase():
    """...existing docstring..."""
    logger.info("=" * 80)
    logger.info("PHASE 1: Merge & Normalize Raw Results")
    logger.info("=" * 80)
    
    if not MERGE_SCRIPT.exists():
        logger.error(f"Merge script not found: {MERGE_SCRIPT}")
        return False
    
    try:
        logger.info(f"Executing: {MERGE_SCRIPT.name}")
        result = subprocess.run(
            [sys.executable, str(MERGE_SCRIPT)],
            cwd=SCRIPT_DIR,
            check=True
        )
        logger.info("✓ Merge phase completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Merge phase failed with exit code {e.returncode}")
        return False
    except Exception as e:
        logger.error(f"✗ Merge phase error: {e}")
        return False


def run_parse_phase():
    """...existing docstring..."""
    logger.info("=" * 80)
    logger.info("PHASE 2: Parse & Compile Empirical Log")
    logger.info("=" * 80)
    
    if not PARSE_SCRIPT.exists():
        logger.error(f"Parse script not found: {PARSE_SCRIPT}")
        return False
    
    try:
        logger.info(f"Executing: {PARSE_SCRIPT.name}")
        result = subprocess.run(
            [sys.executable, str(PARSE_SCRIPT)],
            cwd=SCRIPT_DIR,
            check=True
        )
        logger.info("✓ Parse phase completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Parse phase failed with exit code {e.returncode}")
        return False
    except Exception as e:
        logger.error(f"✗ Parse phase error: {e}")
        return False


def print_summary(merge_success, parse_success, skip_merge, skip_parse, traceability_result=None):
    """Print pipeline execution summary"""
    logger.info("=" * 80)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 80)
    
    if skip_merge:
        logger.info("Phase 1 (Merge):              SKIPPED")
    else:
        status = "✓ SUCCESS" if merge_success else "✗ FAILED"
        logger.info(f"Phase 1 (Merge):              {status}")
    
    if skip_parse:
        logger.info("Phase 2 (Parse):              SKIPPED")
    else:
        status = "✓ SUCCESS" if parse_success else "✗ FAILED"
        logger.info(f"Phase 2 (Parse):              {status}")

    if traceability_result is not None:
        logger.info("Phase 3 (Traceability):       ✓ COMPLETE")
        logger.info(f"  └ Runs linked: {traceability_result.get('evaluation_runs_linked', 0)}")
        logger.info(f"  └ Events linked: {traceability_result.get('chaos_events_linked', 0)}")
        logger.info(f"  └ Orphan events: {traceability_result.get('orphan_events_count', 0)}")
    else:
        logger.info("Phase 3 (Traceability):       SKIPPED (use --with-traceability)")
    
    logger.info("=" * 80)

    # Check for output files
    combined_json = SCRIPT_DIR / 'combined_results.json'
    pristine_csv = SCRIPT_DIR / 'pristine_chaos_vs_repair_matrix.csv'
    trace_json = SCRIPT_DIR / 'results' / 'global_traceability_linked.json'
    
    if combined_json.exists():
        size_mb = combined_json.stat().st_size / 1024 / 1024
        logger.info(f"✓ Outputs: {combined_json.name} ({size_mb:.1f} MB)")
    
    if pristine_csv.exists():
        size_mb = pristine_csv.stat().st_size / 1024 / 1024
        logger.info(f"✓ Outputs: {pristine_csv.name} ({size_mb:.1f} MB)")

    if trace_json.exists():
        size_mb = trace_json.stat().st_size / 1024 / 1024
        logger.info(f"✓ Outputs: {trace_json.name} ({size_mb:.1f} MB)")
    
    logger.info("=" * 80)


def main():
    """Main pipeline orchestration"""
    
    # Parse command-line arguments
    skip_merge = '--skip-merge' in sys.argv
    skip_parse = '--skip-parse' in sys.argv
    with_traceability = '--with-traceability' in sys.argv
    show_help = '--help' in sys.argv or '-h' in sys.argv
    
    if show_help:
        print(__doc__)
        sys.exit(0)
    
    logger.info("Starting Unified Results Processing Pipeline")
    logger.info(f"Working directory: {SCRIPT_DIR}")
    logger.info("")
    
    merge_success = True
    parse_success = True
    traceability_result = None
    
    # Run merge phase
    if not skip_merge:
        merge_success = run_merge_phase()
        logger.info("")
        if not merge_success:
            logger.error("Pipeline halted due to merge phase failure")
            logger.error("To skip merge and proceed to parse, use: --skip-merge")
            print_summary(merge_success, False, skip_merge, skip_parse, None)
            sys.exit(1)
    else:
        logger.info("PHASE 1 (Merge): SKIPPED")
        logger.info("")
    
    # Run parse phase
    if not skip_parse:
        parse_success = run_parse_phase()
        logger.info("")
    else:
        logger.info("PHASE 2 (Parse): SKIPPED")
        logger.info("")

    # Run traceability phase
    if with_traceability:
        logger.info("PHASE 3: Event-Level Traceability Linking")
        logger.info("=" * 80)
        traceability_result = link_events_by_run_id()
        logger.info("")
    else:
        logger.info("PHASE 3 (Traceability): SKIPPED (use --with-traceability)")
        logger.info("")
    
    # Print summary
    print_summary(merge_success, parse_success, skip_merge, skip_parse, traceability_result)
    
    # Exit with appropriate code
    if merge_success and parse_success:
        logger.info("✓ Pipeline execution completed successfully")
        sys.exit(0)
    else:
        logger.error("✗ Pipeline execution encountered errors")
        sys.exit(1)


if __name__ == '__main__':
    main()
