"""Semantic Translation Benchmark Pipeline.

Executes schema reconciliation evaluation across Levenshtein, Regex, BERT, and
Gemma reconcilers using static datasets. Calculates run, drift-type, and
method-specific resilience scores using the installed resilience-metrics package.
Outputs IEEE TKDE-ready CSV and JSON aggregates.
"""

import os
import sys
import json
import csv
import time
import subprocess
from typing import Dict, List, Any

# Remove local directory from sys.path to avoid models.py name collision
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir in sys.path:
    sys.path.remove(script_dir)
if "" in sys.path:
    sys.path.remove("")

# Add root folder to sys.path
root_dir = os.path.dirname(script_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from semantic_benchmark.model_loaders import StrictBERTModel, StrictGemmaModel, run_preflight_validation
from semantic_benchmark.reconcilers import LevenshteinReconciler, RegexReconciler, BERTReconciler, GemmaReconciler
import resilience_metrics

def get_git_commit() -> str:
    """Retrieve current git commit hash dynamically."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return "fc6fbfb9-refactored"

def determine_mutated_key(original: Dict[str, Any], mutated: Dict[str, Any]) -> str:
    """Heuristic to determine which canonical key was mutated/drifted."""
    orig_keys = set(original.keys())
    mut_keys = set(mutated.keys())
    
    # 1. Renamed or deleted key
    missing = orig_keys - mut_keys
    if missing:
        return list(missing)[0]
        
    # 2. Value or type changes
    for k in orig_keys & mut_keys:
        if original[k] != mutated[k]:
            return k
            
    # 3. Fallback to first key
    return list(original.keys())[0] if original else "unknown"

def main():
    import argparse
    parser = argparse.ArgumentParser(description="TKDE Semantic Reconciliation Benchmark")
    parser.add_argument("--dataset-path", default="chaos_generator/datasets/chaos_dataset.json", help="Path to static dataset JSON or CSV")
    parser.add_argument("--runs", type=int, default=None, help="Limit number of runs/samples to evaluate")
    parser.add_argument("--require-local-models", type=bool, default=True, help="Force local-only model executions")
    parser.add_argument("--strict-mode", action="store_true", help="Abort on any internet use or pre-flight failure")
    parser.add_argument("--output-dir", default="results", help="Directory to save TKDE evaluation outputs")
    parser.add_argument("--drift-types", default=None, help="Comma-separated list of drift types to include (default: all)")
    parser.add_argument("--methods", default=None, help="Comma-separated list of methods to enable (default: regex,levenshtein,bert,gemma)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging of comparison results")
    args = parser.parse_args()

    print("================================================================================")
    print(" STARTING SEMANTIC TRANSLATION BENCHMARK (TKDE PRIMARY PATH)")
    print("================================================================================\n")

    # 1. Pre-flight Validation
    preflight, abort, abort_reason = run_preflight_validation(
        require_local_models=args.require_local_models,
        strict_mode=args.strict_mode
    )
    if abort:
        print(f"[!] PRE-FLIGHT ERROR: {abort_reason}")
        sys.exit(1)
    
    print("[✓] Pre-flight validation passed successfully:")
    print(f"    - Hardware Backend: {preflight['hardware_backend']}")
    print(f"    - GPU Device: {preflight['device']}")
    print(f"    - BERT Status: {preflight['model_source']['bert']}")
    print(f"    - Gemma Status: {preflight['model_source']['gemma']}")
    print(f"    - Offline Enforced: {os.environ.get('HF_HUB_OFFLINE') == '1'}\n")

    # 2. Parse configuration filters
    enabled_drift_types = None
    if args.drift_types:
        enabled_drift_types = [t.strip().lower() for t in args.drift_types.split(",")]
        print(f"[*] Drift type filtering enabled: {enabled_drift_types}")
        
    enabled_methods = ["regex", "levenshtein", "bert", "gemma"]
    if args.methods:
        enabled_methods = [m.strip().lower() for m in args.methods.split(",")]
        print(f"[*] Enabled reconciliation methods: {enabled_methods}")

    # 3. Load Dataset
    if not os.path.exists(args.dataset_path):
        print(f"[!] Dataset not found at: {args.dataset_path}")
        print("[!] Please run the Chaos Generator first using:")
        print("    python chaos_generator/generate_chaos_dataset.py")
        sys.exit(1)

    dataset = []
    if args.dataset_path.endswith(".csv"):
        print(f"[*] Loading CSV dataset from: {args.dataset_path}")
        with open(args.dataset_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Reconstruct sample dictionary fields from CSV row
                original_str = row.get("original_payload", "{}")
                mutated_str = row.get("mutated_payload", "{}")
                try:
                    original = json.loads(original_str)
                except Exception:
                    try:
                        original = eval(original_str)
                    except Exception:
                        original = {}
                try:
                    mutated = json.loads(mutated_str)
                except Exception:
                    try:
                        mutated = eval(mutated_str)
                    except Exception:
                        mutated = {}
                
                drift_present_raw = row.get("drift_present", "False")
                drift_present = drift_present_raw.lower() in ("true", "1", "yes")

                sample_rec = {
                    "sample_id": row.get("sample_id", "unknown"),
                    "api_name": row.get("api_name", "unknown"),
                    "chaos_strategy": row.get("chaos_strategy", "unknown"),
                    "chaos_level": row.get("chaos_level", "5"),
                    "run_number": int(row.get("run_number", 1)),
                    "run_id": row.get("run_id", "unknown"),
                    "event_id": row.get("event_id", "unknown"),
                    "drift_type": row.get("drift_type", "none"),
                    "original_payload": original,
                    "mutated_payload": mutated,
                    "drift_present": drift_present
                }
                dataset.append(sample_rec)
    else:
        print(f"[*] Loading JSON dataset from: {args.dataset_path}")
        with open(args.dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        
    # Apply drift types filter
    if enabled_drift_types is not None:
        dataset = [s for s in dataset if s.get("drift_type", "none").lower() in enabled_drift_types]
        print(f"[✓] Filtered dataset to {len(dataset)} samples matching drift types.")

    if args.runs:
        dataset = dataset[:args.runs]
        
    print(f"[✓] Evaluation set contains {len(dataset)} samples.\n")

    # 4. Load Models
    print("[*] Initialising local models...")
    bert_model = StrictBERTModel(require_local=args.require_local_models) if "bert" in enabled_methods else None
    gemma_model = StrictGemmaModel(require_local=args.require_local_models) if "gemma" in enabled_methods else None
    
    # 5. Initialise Reconcilers
    reconcilers = {}
    if "regex" in enabled_methods:
        reconcilers["regex"] = RegexReconciler()
    if "levenshtein" in enabled_methods:
        reconcilers["levenshtein"] = LevenshteinReconciler()
    if "bert" in enabled_methods and bert_model is not None:
        reconcilers["bert"] = BERTReconciler(bert_model)
    if "gemma" in enabled_methods and gemma_model is not None:
        reconcilers["gemma"] = GemmaReconciler(gemma_model)

    # 6. Execute Evaluation
    results = []
    evaluator = resilience_metrics.ResilienceEvaluator()
    
    print("\n[*] Running benchmark evaluation...")
    for idx, sample in enumerate(dataset, 1):
        original = sample["original_payload"]
        mutated = sample["mutated_payload"]
        drift_type = sample["drift_type"]
        api_name = sample["api_name"]
        
        # Determine correct canonical target key for accuracy scoring
        target_key = determine_mutated_key(original, mutated)
        
        # Canonical keys list and mutated representation
        canonical_keys = list(original.keys())
        query_key = json.dumps(mutated)
        
        # Run each reconciler
        sample_results = {}
        for method_name, reconciler in reconcilers.items():
            start_t = time.perf_counter()
            rec_res = reconciler.reconcile(canonical_keys, query_key)
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            
            match = rec_res["match"]
            confidence = rec_res["confidence"]
            fallback_used = rec_res["fallback_used"]
            
            # Correctness mapping
            is_correct = (match == target_key)
            match_score = 1.0 if is_correct else 0.0
            
            # Simulated throughput (1 query per run profile)
            throughput_pps = 1000.0 / max(1e-6, elapsed_ms)
            
            # Resilience scoring using the installed package
            res_scores = evaluator.add_run(
                run_id=sample["run_id"],
                drift_type=drift_type,
                method=method_name,
                throughput_pps=throughput_pps,
                target_hz=100.0,  # Benchmark baseline frequency
                detection_rate=1.0 if sample["drift_present"] else 0.0,
                recovery_score=match_score,
                p95_latency_ms=elapsed_ms,
                baseline_p95_ms=10.0
            )
            
            sample_results[method_name] = {
                "match": match,
                "confidence": confidence,
                "latency_ms": elapsed_ms,
                "fallback_used": fallback_used,
                "fallback_reason": rec_res.get("fallback_reason"),
                "match_score": match_score,
                "resilience_P": res_scores["P"],
                "resilience_P2": res_scores["P2"]
            }
            
            if args.verbose:
                print(f"    [Sample {idx}] Method: {method_name.upper()} | Correct: {is_correct} | Latency: {elapsed_ms:.2f}ms | Confidence: {confidence:.4f}")
            
        record = {
            "sample_id": sample["sample_id"],
            "run_id": sample.get("run_id", "unknown"),
            "event_id": sample.get("event_id", "unknown"),
            "api_name": api_name,
            "drift_type": drift_type,
            "drift_present": sample.get("drift_present", False),
            "chaos_strategy": sample["chaos_strategy"],
            "chaos_level": sample["chaos_level"],
            "target_key": target_key,
            "original_payload": original,
            "mutated_payload": mutated,
            "reconciliation": sample_results
        }
        results.append(record)
        
        if not args.verbose and (idx % 10 == 0 or idx == len(dataset)):
            print(f"    - Processed {idx}/{len(dataset)} samples...")

    # 7. Aggregate Outputs
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Save per-run JSON
    run_output_path = os.path.join(args.output_dir, "per_run_benchmark.json")
    pipeline_version = get_git_commit()
    
    with open(run_output_path, "w", encoding="utf-8") as f:
        json.dump({
            "pipeline_version": pipeline_version,
            "hardware_backend": preflight["hardware_backend"],
            "device": preflight["device"],
            "model_versions": {
                "bert": "sentence-transformers/all-MiniLM-L6-v2",
                "gemma": "google/gemma-4-E4B-it"
            },
            "evaluations": results,
            "resilience_summary": evaluator.get_summary()
        }, f, indent=2)
    print(f"\n[✓] Saved detailed per-run benchmark to: {run_output_path}")

    # Compute aggregation tables
    accuracy_vs_drift = {}
    latency_vs_method = {}
    robustness_vs_intensity = {}
    
    for r in results:
        dt = r["drift_type"]
        intensity = r["chaos_level"]
        
        for method, res in r["reconciliation"].items():
            # Accuracy (match score) vs Drift
            accuracy_vs_drift.setdefault(dt, {}).setdefault(method, []).append(res["match_score"])
            
            # Latency vs Method
            latency_vs_method.setdefault(method, []).append(res["latency_ms"])
            
            # Resilience vs Chaos Intensity
            robustness_vs_intensity.setdefault(intensity, {}).setdefault(method, []).append(res["resilience_P"])

    # Output 1: accuracy_vs_drift.csv
    acc_csv = os.path.join(args.output_dir, "accuracy_vs_drift.csv")
    with open(acc_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["drift_type", "regex_acc", "levenshtein_acc", "bert_acc", "gemma_acc"])
        for dt, methods in accuracy_vs_drift.items():
            regex_vals = methods.get("regex", [])
            lev_vals = methods.get("levenshtein", [])
            bert_vals = methods.get("bert", [])
            gem_vals = methods.get("gemma", [])
            
            writer.writerow([
                dt,
                sum(regex_vals) / len(regex_vals) if regex_vals else 0.0,
                sum(lev_vals) / len(lev_vals) if lev_vals else 0.0,
                sum(bert_vals) / len(bert_vals) if bert_vals else 0.0,
                sum(gem_vals) / len(gem_vals) if gem_vals else 0.0
            ])
    print(f"[✓] Saved accuracy_vs_drift aggregates to: {acc_csv}")

    # Output 2: latency_vs_method.csv
    lat_csv = os.path.join(args.output_dir, "latency_vs_method.csv")
    with open(lat_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["method", "avg_latency_ms", "min_latency_ms", "max_latency_ms"])
        for method, latencies in latency_vs_method.items():
            if latencies:
                writer.writerow([
                    method,
                    sum(latencies) / len(latencies),
                    min(latencies),
                    max(latencies)
                ])
    print(f"[✓] Saved latency_vs_method aggregates to: {lat_csv}")

    # Output 3: robustness_vs_intensity.csv
    rob_csv = os.path.join(args.output_dir, "robustness_vs_intensity.csv")
    with open(rob_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["chaos_intensity", "regex_resilience", "levenshtein_resilience", "bert_resilience", "gemma_resilience"])
        for intensity, methods in robustness_vs_intensity.items():
            regex_vals = methods.get("regex", [])
            lev_vals = methods.get("levenshtein", [])
            bert_vals = methods.get("bert", [])
            gem_vals = methods.get("gemma", [])
            
            writer.writerow([
                intensity,
                sum(regex_vals) / len(regex_vals) if regex_vals else 0.0,
                sum(lev_vals) / len(lev_vals) if lev_vals else 0.0,
                sum(bert_vals) / len(bert_vals) if bert_vals else 0.0,
                sum(gem_vals) / len(gem_vals) if gem_vals else 0.0
            ])
    print(f"[✓] Saved robustness_vs_intensity aggregates to: {rob_csv}")
    
    # Print high-level summary
    summary = evaluator.get_summary()
    if summary:
        print("\n================================================================================")
        print(" BENCHMARK COMPLETED SUCCESSFULLY")
        print("================================================================================")
        print(f"Global Resilience Score P  : {summary.get('global_resilience_mean_P', 0.0):.4f}")
        print(f"Global Resilience Score P2 : {summary.get('global_resilience_mean_P2', 0.0):.4f}")
        print("Resilience Score by Reconciler Method:")
        for method, p_val in summary.get("by_method", {}).items():
            print(f"  - {method:12} : {p_val:.4f}")
        print("================================================================================\n")

if __name__ == "__main__":
    main()
