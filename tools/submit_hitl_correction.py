#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.

"""
HITL Correction CLI
===================
Manual override tool for research leads to correct semantic drift.
Usage: python3 tools/submit_hitl_correction.py --drifted velocity_kph --canonical speed
"""

import argparse
import sys
import os

# Support imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from modules.hitl_feedback import HITLFeedbackManager
from tools.reconciliation_ablation_study import CANONICAL_SCHEMA

def main():
    parser = argparse.ArgumentParser(description="Submit a Human-in-the-Loop (HITL) correction.")
    parser.add_argument("--drifted", help="The drifted/noisy field name (e.g. 'spid')")
    parser.add_argument("--canonical", help="The target canonical name (e.g. 'speed')")
    parser.add_argument("--list-quarantine", action="store_true", help="List all pending Tier 3 drift cases.")
    
    args = parser.parse_args()
    
    quarantine_path = "data/quarantine_log.json"
    
    if args.list_quarantine:
        import json
        if not os.path.exists(quarantine_path):
            print("No pending quarantine cases.")
            return
        with open(quarantine_path, 'r') as f:
            log = json.load(f)
        if not log:
            print("Quarantine log is empty.")
            return
        
        print("\n[ Tier 3: Pending Research Quarantine ]")
        print("-" * 40)
        for entry in log:
            print(f"Drifted:   {entry['original']}")
            print(f"BERT Guess: {entry['suggested']} ({entry['confidence']})")
            print(f"Detected:  {entry['timestamp']}")
            print("-" * 40)
        return

    if not args.drifted or not args.canonical:
        parser.print_help()
        sys.exit(1)
    
    if args.canonical not in CANONICAL_SCHEMA:
        print(f"Error: '{args.canonical}' is not in the canonical schema.")
        print(f"Available: {CANONICAL_SCHEMA}")
        sys.exit(1)
        
    manager = HITLFeedbackManager()
    manager.add_correction(args.drifted, args.canonical)
    
    # Cleanup quarantine log if it was recorded
    if os.path.exists(quarantine_path):
        import json
        with open(quarantine_path, 'r') as f:
            log = json.load(f)
        new_log = [e for e in log if e["original"] != args.drifted]
        with open(quarantine_path, 'w') as f:
            json.dump(new_log, f, indent=4)
    
    print(f"Successfully recorded HITL correction: '{args.drifted}' -> '{args.canonical}'")
    print("This mapping has been ingested into the Tier 1 Verified Cache.")

if __name__ == "__main__":
    main()
