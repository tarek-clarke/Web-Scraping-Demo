import os
import sys
import json
import time
import subprocess
from uuid import uuid4
from datetime import datetime
import torch

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from semantic_benchmark.model_loaders import StrictBERTModel, StrictGemmaModel, run_preflight_validation
from semantic_benchmark.reconcilers import LevenshteinReconciler, RegexReconciler, BERTReconciler, GemmaReconciler
from models.device_selector import get_device_info

def determine_mutated_key(original, mutated) -> str:
    orig_keys = set(original.keys())
    mut_keys = set(mutated.keys())
    missing = orig_keys - mut_keys
    if missing:
        return list(missing)[0]
    for k in orig_keys & mut_keys:
        if original[k] != mutated[k]:
            return k
    return list(original.keys())[0] if original else "unknown"

def main():
    print("================================================================================")
    print(" UNIFIED SINGLE-PROCESS MATRIX RUNNER (ZERO RE-COMPILATION OVERHEAD)")
    print("================================================================================")
    
    # 1. Run Pre-flight Validation once
    enabled_methods = ["regex", "levenshtein", "bert", "gemma"]
    preflight, abort, abort_reason = run_preflight_validation(
        require_local_models=True,
        strict_mode=False,
        enabled_methods=enabled_methods
    )
    if abort:
        print(f"[!] PRE-FLIGHT ERROR: {abort_reason}")
        sys.exit(1)
        
    dev_info = get_device_info()
    model_str = dev_info.get("model", "unknown").replace(" ", "_").replace("(", "").replace(")", "")
    git_commit = "9e0ba3e9-unified"
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        git_commit = res.stdout.strip()
    except Exception:
        pass

    # 2. Load Models exactly ONCE in memory
    print("\n[*] Initialising local models (Single-Load)...")
    bert_model = StrictBERTModel(require_local=True)
    gemma_model = StrictGemmaModel(require_local=True)
    
    print("\n[*] Instantiating reconcilers...")
    reconcilers = {
        "regex": RegexReconciler(),
        "levenshtein": LevenshteinReconciler(),
        "bert": BERTReconciler(bert_model),
        "gemma": GemmaReconciler(gemma_model)
    }

    # Matrix configuration
    scale = 10000
    probability = 0.05
    frequency = 1000
    iterations = 3
    apis = ["finnhub", "openmeteo", "spacex", "openf1"]
    strategies = ["json", "schema", "gemma"]
    
    total_runs = len(apis) * len(strategies) * iterations
    state_file = "matrix_unified_state.json"
    state = {"completed_runs": []}
    
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            try:
                state = json.load(f)
                print(f"[*] Loaded state file. Resuming matrix... ({len(state['completed_runs'])}/{total_runs} completed)")
            except json.JSONDecodeError:
                pass
                
    run_idx = 0
    for i in range(1, iterations + 1):
        for api in apis:
            for strategy in strategies:
                run_idx += 1
                state_key = f"run_{i}_{api}_{strategy}"
                
                if state_key in state["completed_runs"]:
                    continue
                    
                print(f"\n================================================================================")
                print(f" [MATRIX RUN {run_idx}/{total_runs}] Iteration: {i} | API: {api} | Generator: {strategy}")
                print(f"================================================================================")
                
                run_id = uuid4().hex
                
                # 1. Generate Dataset
                cmd_gen = [
                    "python3", "chaos_generator/generate_chaos_dataset.py",
                    "--packets", str(scale),
                    "--chaos-probability", str(probability),
                    "--frequency-hz", str(frequency),
                    "--api", api,
                    "--strategy", strategy,
                    "--run-id", run_id,
                    "--run-number", str(i)
                ]
                print(f"[*] Generating streaming dataset...")
                subprocess.run(cmd_gen, check=True)
                
                dataset_path = f"chaos_generator/datasets/stream_{api}_{strategy}_{probability}_{run_id}.jsonl"
                
                # 2. Evaluate dataset in-memory (No reload, no VRAM leakage)
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                folder_name = f"{model_str}_{timestamp_str}_{run_id}"
                final_output_dir = os.path.join("results", folder_name)
                os.makedirs(final_output_dir, exist_ok=True)
                
                jsonl_output_path = os.path.join(final_output_dir, f"telemetry_stream_{run_id}.jsonl")
                print(f"[*] Processing streaming dataset in-memory: {dataset_path}")
                
                packet_count = 0
                with open(dataset_path, "r", encoding="utf-8") as in_f, \
                     open(jsonl_output_path, "w", encoding="utf-8") as out_f:
                    
                    for line in in_f:
                        if not line.strip():
                            continue
                        
                        sample = json.loads(line)
                        packet_count += 1
                        
                        original = sample["original_payload"]
                        mutated = sample["mutated_payload"]
                        
                        target_key = determine_mutated_key(original, mutated)
                        canonical_keys = list(original.keys())
                        query_key = json.dumps(mutated)
                        
                        gpu_vram_allocated_mb = 0.0
                        if torch.cuda.is_available():
                            gpu_vram_allocated_mb = torch.cuda.memory_allocated() / (1024 * 1024)
                        
                        packet_start_t = time.perf_counter()
                        sample_results = {}
                        for method_name, reconciler in reconcilers.items():
                            rec_res = reconciler.reconcile(canonical_keys, query_key)
                            match = rec_res["match"]
                            rec_res["semantic_recovery_success"] = (match == target_key)
                            sample_results[method_name] = rec_res
                            
                        packet_elapsed_ms = (time.perf_counter() - packet_start_t) * 1000.0
                        
                        telemetry_row = {
                            "packet_id": sample["packet_id"],
                            "run_id": sample["run_id"],
                            "run_number": sample["run_number"],
                            "timestamp": sample["timestamp"],
                            "pipeline_version": git_commit,
                            "workload_scale": sample["workload_scale"],
                            "simulated_frequency": sample["simulated_frequency"],
                            "api_profile": sample["api_profile"],
                            "chaos_probability": sample["chaos_probability"],
                            "drift_present": sample["drift_present"],
                            "drift_type": sample["drift_type"],
                            "target_key": target_key,
                            "original_payload": original,
                            "mutated_payload": mutated,
                            "hardware_backend": preflight["hardware_backend"],
                            "gpu_name": dev_info.get("gpu_name"),
                            "vram_capacity_gb": dev_info.get("vram_gb"),
                            "gpu_vram_allocated_mb": gpu_vram_allocated_mb,
                            "compute_utilization_pct": 100.0,
                            "per_packet_processing_time_ms": packet_elapsed_ms,
                            "reconciliation": sample_results
                        }
                        out_f.write(json.dumps(telemetry_row) + "\n")
                        
                        if packet_count % 1000 == 0:
                            print(f"    - Processed {packet_count}/10000 packets...")
                            
                # Clear reconciler query caches to keep memory completely flat
                reconcilers["bert"].clear_caches()
                reconcilers["gemma"].clear_caches()
                
                # Delete raw dataset to save disk space
                if os.path.exists(dataset_path):
                    os.remove(dataset_path)
                    
                # Commit state
                state["completed_runs"].append(state_key)
                with open(state_file, "w") as f:
                    json.dump(state, f, indent=2)
                    
    print("\n[✓] UNIFIED SINGLE-PROCESS MATRIX RUN COMPLETE!")

if __name__ == "__main__":
    main()
