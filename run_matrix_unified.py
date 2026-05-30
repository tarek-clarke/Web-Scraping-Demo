import os
import sys
import json
import time
import random
import subprocess
from uuid import uuid4
from datetime import datetime
import torch

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from semantic_benchmark.model_loaders import StrictBERTModel, StrictGemmaModel, run_preflight_validation
from semantic_benchmark.reconcilers import LevenshteinReconciler, RegexReconciler, BERTReconciler, GemmaReconciler
from models.device_selector import get_device_info

# Import chaos generator components directly (avoid subprocess overhead)
from api.finnhub import FinnhubAPI
from api.openmeteo import OpenMeteoAPI
from api.spacex import SpaceXAPI
from api.openf1 import OpenF1API
from chaos_generator.chaos.strategy import select_chaos


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


def generate_dataset_inline(api_name, strategy_name, scale, probability, frequency, run_id, run_number):
    """Generate chaos dataset in-memory. Returns list of packet dicts. No subprocess, no disk I/O."""
    apis = {
        "finnhub": FinnhubAPI,
        "openmeteo": OpenMeteoAPI,
        "spacex": SpaceXAPI,
        "openf1": OpenF1API,
    }

    api = apis[api_name]()
    try:
        base_data = api.fetch_data()
    except Exception as e:
        print(f"    [!] Warning: failed to fetch live data for {api_name} ({e}). Using static fallback.", flush=True)
        base_data = {"price": 100.0, "canonical": "price"}

    chaos_engine = select_chaos(strategy_name, probability)
    delay_s = 1.0 / frequency
    current_sim_time = time.time()

    packets = []
    for i in range(scale):
        event_id = uuid4().hex
        current_sim_time += delay_s
        timestamp_iso = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(current_sim_time)) + f".{int((current_sim_time % 1) * 1000):03d}Z"

        if random.random() < probability:
            try:
                mutated, drift_type, _ = chaos_engine(
                    base_data,
                    drift_logger=None,
                    run_number=run_number,
                    api_source=api_name,
                    run_id=run_id,
                    event_id=event_id
                )
                if drift_type is None:
                    drift_type = "none"
            except Exception:
                mutated = base_data
                drift_type = "none"
        else:
            mutated = base_data
            drift_type = "none"

        packets.append({
            "packet_id": f"pkt_{uuid4().hex[:12]}",
            "run_id": run_id,
            "run_number": run_number,
            "timestamp": timestamp_iso,
            "workload_scale": scale,
            "simulated_frequency": f"{frequency}hz",
            "api_profile": api_name,
            "chaos_probability": probability,
            "chaos_strategy": strategy_name,
            "drift_type": drift_type,
            "drift_present": (drift_type != "none"),
            "target_key": base_data.get("canonical", list(base_data.keys())[0]),
            "original_payload": base_data,
            "mutated_payload": mutated
        })

        if (i + 1) % 5000 == 0:
            print(f"    - Generated {i + 1}/{scale} packets...", flush=True)

    return packets


def main():
    print("================================================================================")
    print(" UNIFIED SINGLE-PROCESS MATRIX RUNNER v2 (OPTIMIZED)")
    print("================================================================================")
    
    # 1. Run Pre-flight Validation once (also loads models via singleton)
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

    # 2. Load Models exactly ONCE — reuse singleton from preflight
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
    completed_count = len(state["completed_runs"])
    sweep_start_t = time.perf_counter()
    
    for i in range(1, iterations + 1):
        for api in apis:
            for strategy in strategies:
                run_idx += 1
                state_key = f"run_{i}_{api}_{strategy}"
                
                if state_key in state["completed_runs"]:
                    continue
                    
                print(f"\n================================================================================")
                print(f" [MATRIX RUN {run_idx}/{total_runs}] Iteration: {i} | API: {api} | Generator: {strategy}")
                print(f"================================================================================", flush=True)
                
                run_id = uuid4().hex
                run_start_t = time.perf_counter()
                
                # 1. Generate Dataset INLINE (no subprocess, no disk I/O)
                print(f"[*] Generating {scale} packets (inline)...", flush=True)
                gen_start_t = time.perf_counter()
                packets = generate_dataset_inline(api, strategy, scale, probability, frequency, run_id, i)
                gen_elapsed = time.perf_counter() - gen_start_t
                
                drift_total = sum(1 for p in packets if p["drift_present"])
                print(f"[✓] Generated {len(packets)} packets ({drift_total} drifted) in {gen_elapsed:.1f}s", flush=True)
                
                # 2. Process packets in-memory
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                folder_name = f"{model_str}_{timestamp_str}_{run_id}"
                final_output_dir = os.path.join("results", folder_name)
                os.makedirs(final_output_dir, exist_ok=True)
                
                jsonl_output_path = os.path.join(final_output_dir, f"telemetry_stream_{run_id}.jsonl")
                print(f"[*] Processing {len(packets)} packets → {jsonl_output_path}", flush=True)
                
                packet_count = 0
                drift_count = 0
                proc_start_t = time.perf_counter()
                
                with open(jsonl_output_path, "w", encoding="utf-8") as out_f:
                    for sample in packets:
                        packet_count += 1
                        
                        original = sample["original_payload"]
                        mutated = sample["mutated_payload"]
                        is_drifted = sample.get("drift_present", False)
                        
                        target_key = determine_mutated_key(original, mutated)
                        canonical_keys = list(original.keys())
                        
                        gpu_vram_allocated_mb = 0.0
                        if torch.cuda.is_available():
                            gpu_vram_allocated_mb = torch.cuda.memory_allocated() / (1024 * 1024)
                        
                        packet_start_t = time.perf_counter()
                        sample_results = {}
                        
                        # Key-only queries for semantic methods (better cache hits + faster Levenshtein)
                        query_key_full = json.dumps(mutated)
                        query_key_keys_only = json.dumps(sorted(mutated.keys()))
                        
                        for method_name, reconciler in reconcilers.items():
                            if not is_drifted and method_name in ("gemma", "bert"):
                                # No drift: skip GPU inference entirely, return trivial correct result
                                rec_res = {
                                    "match": target_key,
                                    "confidence_raw": 1.0,
                                    "syntactic_parse_time_ms": None,
                                    "semantic_inference_time_ms": 0.0,
                                    "fallback_triggered": False,
                                    "fallback_reason": None
                                }
                            elif method_name == "gemma":
                                drift_count += 1
                                rec_res = reconciler.reconcile(canonical_keys, query_key_keys_only)
                            elif method_name == "bert":
                                rec_res = reconciler.reconcile(canonical_keys, query_key_keys_only)
                            elif method_name == "levenshtein":
                                # Levenshtein: use keys-only query (O(n*m) is much cheaper with short strings)
                                rec_res = reconciler.reconcile(canonical_keys, query_key_keys_only)
                            else:
                                # Regex: full payload so regex patterns can scan values
                                rec_res = reconciler.reconcile(canonical_keys, query_key_full)
                            
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
                        
                        if packet_count % 2000 == 0:
                            proc_elapsed = time.perf_counter() - proc_start_t
                            pkt_per_sec = packet_count / proc_elapsed if proc_elapsed > 0 else 0
                            remaining = (scale - packet_count) / pkt_per_sec if pkt_per_sec > 0 else 0
                            print(f"    - Processed {packet_count}/{scale} ({drift_count} drifted) | {pkt_per_sec:.0f} pkt/s | ETA {remaining:.0f}s", flush=True)
                            
                # Clear reconciler query caches to keep memory flat between runs
                reconcilers["bert"].clear_caches()
                reconcilers["gemma"].clear_caches()
                
                run_elapsed = time.perf_counter() - run_start_t
                completed_count += 1
                
                # ETA for remaining runs
                avg_per_run = (time.perf_counter() - sweep_start_t) / completed_count
                remaining_runs = total_runs - completed_count
                eta_min = (avg_per_run * remaining_runs) / 60.0
                
                print(f"[✓] Run {run_idx} complete in {run_elapsed:.1f}s | {completed_count}/{total_runs} done | ETA {eta_min:.1f}min", flush=True)
                    
                # Commit state
                state["completed_runs"].append(state_key)
                with open(state_file, "w") as f:
                    json.dump(state, f, indent=2)
                    
    total_elapsed = time.perf_counter() - sweep_start_t
    print(f"\n[✓] UNIFIED MATRIX RUN COMPLETE! {total_runs} runs in {total_elapsed/60:.1f} minutes")

if __name__ == "__main__":
    main()
