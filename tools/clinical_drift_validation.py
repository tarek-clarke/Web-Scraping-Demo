#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.

"""
Clinical Drift Validation Suite
===============================
Validates the 3-Tier Reconciliation Architecture against medical telemetry.
Measures BERT's semantic accuracy on clinical synonyms (Heart Rate, SpO2, BP).
"""

import sys
import os
import time
from typing import List, Dict

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from modules.enhanced_translator import EnhancedSemanticTranslator
from data.generators.clinical_vitals import ClinicalVitalsGenerator, DRIFT_MAP

def run_validation(n_packets: int = 50):
    print(f"Starting Clinical Drift Validation (N={n_packets})...")
    
    # Passing the Clinical Canonical Schema to the BERT Translator
    clinical_fields = list(DRIFT_MAP.keys())
    translator = EnhancedSemanticTranslator(canonical_schema=clinical_fields)
    gen = ClinicalVitalsGenerator(drift_probability=1.0) # Force drift for all packets
    
    results = []
    correct = 0
    total = 0
    
    # Track performance per vitals category
    category_stats = {cat: {"correct": 0, "total": 0} for cat in DRIFT_MAP.keys()}

    for i in range(n_packets):
        packet = gen.generate_packet()
        drifted_fields = [k for k in packet.keys() if k not in ["patient_id", "timestamp"]]
        
        for field in drifted_fields:
            # Determine ground truth category
            ground_truth = None
            for cat, synonyms in DRIFT_MAP.items():
                if field in synonyms:
                    ground_truth = cat
                    break
            
            if not ground_truth:
                continue # Skip non-drifted fields if any
            
            total += 1
            category_stats[ground_truth]["total"] += 1
            
            # Reconcile
            translation = translator.translate(field)
            mapped_field = translation["mapped"]
            
            is_correct = (mapped_field == ground_truth)
            if is_correct:
                correct += 1
                category_stats[ground_truth]["correct"] += 1
            
            results.append({
                "drifted": field,
                "target": ground_truth,
                "reconciled": mapped_field,
                "confidence": translation["confidence"],
                "correct": is_correct
            })

    # Summary
    print("\n[ Clinical Reconciliation Results ]")
    print("-" * 40)
    for cat, stats in category_stats.items():
        acc = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"{cat:<15}: {acc:>6.1f}% ({stats['correct']}/{stats['total']})")
    
    global_acc = (correct / total * 100) if total > 0 else 0
    print("-" * 40)
    print(f"GLOBAL ACCURACY: {global_acc:>6.1f}%")
    print(f"Total Drifted Fields: {total}")

if __name__ == "__main__":
    run_validation()
