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
    parser.add_argument("--drifted", required=True, help="The drifted/noisy field name (e.g. 'spid')")
    parser.add_argument("--canonical", required=True, help="The target canonical name (e.g. 'speed')")
    
    args = parser.parse_args()
    
    if args.canonical not in CANONICAL_SCHEMA:
        print(f"Error: '{args.canonical}' is not in the canonical schema.")
        print(f"Available: {CANONICAL_SCHEMA}")
        sys.exit(1)
        
    manager = HITLFeedbackManager()
    manager.add_correction(args.drifted, args.canonical)
    
    print(f"Successfully recorded HITL correction: '{args.drifted}' -> '{args.canonical}'")
    print("This mapping will now be used as a primary override in the EnhancedSemanticTranslator.")

if __name__ == "__main__":
    main()
