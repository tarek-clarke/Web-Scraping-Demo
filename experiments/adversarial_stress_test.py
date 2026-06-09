#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.

"""
Adversarial Stress Test (N=1000)
================================
Thesis Validation: Resilience under extreme schema entropy.
Uses the DriftSimulator to generate 1000 noisy samples and measures
reconciliation accuracy across BERT, Levenshtein, and Regex.
"""

import os
import sys
import json
import time
import numpy as np
import difflib
from typing import List, Dict
from rich.console import Console
from rich.table import Table

# Support imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from modules.enhanced_translator import EnhancedSemanticTranslator
from tests.chaos_engine import DriftSimulator, EntropyType
from tools.reconciliation_ablation_study import CANONICAL_SCHEMA

console = Console()

# Standalone Reconciliation Logic for Stress Test
REGEX_KEYWORDS = {
    "speed": ["velo", "spid", "rate", "pace", "kph", "mph"],
    "rpm": ["rev", "tach", "eng_spd"],
    "throttle": ["gas", "accel", "pedal", "pos"],
    "brake_temp": ["brk", "thermal", "disc", "friction"],
    "engine_temp": ["cool", "thermal", "h2o", "deg_c"],
    "oil_pressure": ["lube", "psi", "bar", "press"],
    "oil_temp": ["lube", "thermal", "oil_c"],
    "fuel_level": ["gas", "petrol", "lvl", "pct"],
}

def reconcile_levenshtein_standalone(drifted: str) -> str:
    best_match = ""
    best_score = 0.0
    for canonical in CANONICAL_SCHEMA:
        score = difflib.SequenceMatcher(None, drifted, canonical).ratio()
        if score > best_score:
            best_score = score
            best_match = canonical
    return best_match

def reconcile_regex_standalone(drifted: str) -> str:
    drifted_lower = drifted.lower()
    for canonical, keywords in REGEX_KEYWORDS.items():
        if canonical in drifted_lower: return canonical
        for k in keywords:
            if k in drifted_lower: return canonical
    return "unknown"

def run_stress_test(num_trials: int = 1000):
    console.print(f"\n[bold red]STRESS TEST: {num_trials} ADVERSARIAL TRIALS[/bold red]")
    
    # Initialize components
    translator = EnhancedSemanticTranslator(CANONICAL_SCHEMA)
    simulator = DriftSimulator(clean_names=CANONICAL_SCHEMA)
    
    results = {
        "BERT": {"correct": 0, "latencies": []},
        "LEVEN": {"correct": 0, "latencies": []},
        "REGEX": {"correct": 0, "latencies": []}
    }
    
    per_type_stats = {etype: {"total": 0, "BERT": 0, "LEVEN": 0, "REGEX": 0} for etype in EntropyType}

    console.print(f"Generating and testing {num_trials} drift events...")
    
    for clean, drifted, etype in simulator.stream_chaos(num_samples=num_trials):
        per_type_stats[etype]["total"] += 1
        
        # 1. BERT
        start = time.perf_counter()
        b_res = translator.translate(drifted)["mapped"]
        results["BERT"]["latencies"].append((time.perf_counter() - start) * 1000)
        if b_res == clean:
            results["BERT"]["correct"] += 1
            per_type_stats[etype]["BERT"] += 1
            
        # 2. Levenshtein
        start_l = time.perf_counter()
        l_res = reconcile_levenshtein_standalone(drifted)
        results["LEVEN"]["latencies"].append((time.perf_counter() - start_l) * 1000)
        if l_res == clean:
            results["LEVEN"]["correct"] += 1
            per_type_stats[etype]["LEVEN"] += 1
            
        # 3. Regex
        start_r = time.perf_counter()
        r_res = reconcile_regex_standalone(drifted)
        results["REGEX"]["latencies"].append((time.perf_counter() - start_r) * 1000)
        if r_res == clean:
            results["REGEX"]["correct"] += 1
            per_type_stats[etype]["REGEX"] += 1

    # Print Summary Table
    table = Table(title=f"Adversarial Stress Test Results (n={num_trials})")
    table.add_column("Algorithm", style="cyan")
    table.add_column("Accuracy", justify="right")
    table.add_column("Avg Latency (ms)", justify="right")
    
    for algo in ["BERT", "LEVEN", "REGEX"]:
        acc = results[algo]["correct"] / num_trials
        lat = float(np.mean(results[algo]["latencies"]))
        table.add_row(algo, f"{acc:.1%}", f"{lat:.3f}")
        
    console.print(table)
    
    # Per-Type Breakdown
    type_table = Table(title="Drift Type Breakdown")
    type_table.add_column("Entropy Type")
    type_table.add_column("Count")
    type_table.add_column("BERT")
    type_table.add_column("LEVEN")
    type_table.add_column("REGEX")
    
    for etype, stats in per_type_stats.items():
        if stats["total"] == 0: continue
        type_table.add_row(
            etype.value,
            str(stats["total"]),
            f"{stats['BERT']/stats['total']:.1%}",
            f"{stats['LEVEN']/stats['total']:.1%}",
            f"{stats['REGEX']/stats['total']:.1%}"
        )
    console.print(type_table)

    # Export to JSON
    report = {
        "config": {"n": num_trials, "schema_size": len(CANONICAL_SCHEMA)},
        "global_accuracy": {a: float(results[a]["correct"]/num_trials) for a in results},
        "per_type_stats": {k.value: v for k, v in per_type_stats.items()}
    }
    
    os.makedirs("data/reports", exist_ok=True)
    with open("data/reports/adversarial_stress_test.json", "w") as f:
        json.dump(report, f, indent=4)
        
    console.print(f"\n[bold green]Adversarial stress test complete. Report saved to data/reports/adversarial_stress_test.json[/bold green]")

if __name__ == "__main__":
    run_stress_test(1000)
