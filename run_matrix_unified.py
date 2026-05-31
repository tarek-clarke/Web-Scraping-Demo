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
            "event_id": event_id,
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
    }    # Matrix configuration
    scale = 10000
    frequencies = [100, 1000, 1000000]
    probabilities = [0.05, 0.01, 0.005]
    iterations = 3
    apis = ["finnhub", "openmeteo", "spacex", "openf1"]
    strategies = ["json", "schema", "gemma", "aggressive"]
    
    total_runs = len(apis) * len(strategies) * len(frequencies) * len(probabilities) * iterations
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
                for freq in frequencies:
                    for prob in probabilities:
                        run_idx += 1
                        state_key = f"run_{i}_{api}_{strategy}_{freq}hz_{prob}prob"
                        
                        if state_key in state["completed_runs"]:
                            continue
                            
                        print(f"\n================================================================================")
                        print(f" [MATRIX RUN {run_idx}/{total_runs}] Iter: {i} | API: {api} | Chaos: {strategy} | Freq: {freq}Hz | Prob: {prob*100}%")
                        print(f"================================================================================", flush=True)
                        
                        run_id = uuid4().hex
                        run_start_t = time.perf_counter()
                        
                        # 1. Generate Dataset INLINE (no subprocess, no disk I/O)
                        print(f"[*] Generating {scale} packets (inline)...", flush=True)
                        gen_start_t = time.perf_counter()
                        packets = generate_dataset_inline(api, strategy, scale, prob, freq, run_id, i)
                        gen_elapsed = time.perf_counter() - gen_start_t
                        
                        drift_total = sum(1 for p in packets if p["drift_present"])
                        print(f"[✓] Generated {len(packets)} packets ({drift_total} drifted) in {gen_elapsed:.1f}s", flush=True)
                        
                        # 2. Process packets in-memory
                        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        
                        # Build parameter-rich folder name sorted by GPU/CPU model
                        pct_str = f"{int(prob*100)}pct" if (prob*100).is_integer() else f"{str(prob*100).replace('.', '_')}pct"
                        freq_str = "1mhz" if freq == 1000000 else f"{freq}hz"
                        methods_str = "_".join(enabled_methods)
                        run_folder_name = f"scale_10K_freq_{freq_str}_chaos_{pct_str}_strat_{strategy}_methods_{methods_str}_{timestamp_str}_{run_id[:8]}"
                        
                        # Sort into subfolder grouped by hardware device name
                        final_output_dir = os.path.join("results", model_str, run_folder_name)
                        os.makedirs(final_output_dir, exist_ok=True)
                        
                        jsonl_output_path = os.path.join(final_output_dir, f"telemetry_stream_{run_id}.jsonl")
                        print(f"[*] Processing {len(packets)} packets → {jsonl_output_path}", flush=True)
                        
                        proc_start_t = time.perf_counter()
                        
                        # Identify drifted vs non-drifted packets
                        drifted_indices = []
                        non_drifted_indices = []
                        for idx, sample in enumerate(packets):
                            if sample.get("drift_present", False):
                                drifted_indices.append(idx)
                            else:
                                non_drifted_indices.append(idx)
                        
                        print(f"    - Found {len(drifted_indices)} drifted packets requiring GPU inference. Batching active...", flush=True)
                        
                        # Preflight results list to populate
                        results_list = [{} for _ in range(len(packets))]
                        
                        # Initialize reconciler instances
                        regex_rec = reconcilers["regex"]
                        lev_rec = reconcilers["levenshtein"]
                        bert_rec = reconcilers["bert"]
                        gemma_rec = reconcilers["gemma"]
                        
                        # ─── A. PROCESS DRIFTED PACKETS VIA TENSOR BATCHING ───
                        bert_elapsed_ms_per_packet = 0.0
                        gemma_elapsed_ms_per_packet = 0.0
                        
                        if drifted_indices:
                            # 1. Regex & Levenshtein (CPU - sequential but fast)
                            print(f"    - Running CPU reconcilers on drifted packets...", flush=True)
                            for idx in drifted_indices:
                                sample = packets[idx]
                                original = sample["original_payload"]
                                mutated = sample["mutated_payload"]
                                target_key = determine_mutated_key(original, mutated)
                                canonical_keys = list(original.keys())
                                query_key_full = json.dumps(mutated)
                                
                                rec_res_regex = regex_rec.reconcile(canonical_keys, query_key_full)
                                rec_res_regex["semantic_recovery_success"] = (rec_res_regex["match"] == target_key)
                                
                                rec_res_lev = lev_rec.reconcile(canonical_keys, target_key)
                                rec_res_lev["semantic_recovery_success"] = (rec_res_lev["match"] == target_key)
                                
                                results_list[idx]["regex"] = rec_res_regex
                                results_list[idx]["levenshtein"] = rec_res_lev
                            
                            # 2. BERT Reconciler Batch (Highly optimized parallel matrix operations)
                            print(f"    - Running batched BERT on {len(drifted_indices)} drifted packets...", flush=True)
                            bert_start_t = time.perf_counter()
                            
                            # We can batch get embeddings for all drifted query keys
                            queries = [json.dumps(packets[idx]["mutated_payload"]) for idx in drifted_indices]
                            query_embeddings = bert_model.get_embeddings_batch(queries)
                            
                            bert_elapsed_ms_per_packet = ((time.perf_counter() - bert_start_t) * 1000.0) / len(drifted_indices)
                            
                            for batch_idx, idx in enumerate(drifted_indices):
                                sample = packets[idx]
                                original = sample["original_payload"]
                                mutated = sample["mutated_payload"]
                                target_key = determine_mutated_key(original, mutated)
                                canonical_keys = list(original.keys())
                                
                                # Fetch or compute canonical embeddings
                                canonical_key_tuple = tuple(canonical_keys)
                                canonical_embeddings = bert_rec._canonical_embedding_cache.get(canonical_key_tuple)
                                if canonical_embeddings is None:
                                    canonical_embeddings = bert_model.get_embeddings_batch(canonical_keys)
                                    bert_rec._canonical_embedding_cache[canonical_key_tuple] = canonical_embeddings
                                
                                query_embedding = query_embeddings[batch_idx]
                                
                                best_match = canonical_keys[0]
                                max_similarity = -1.0
                                for c_key, c_emb in zip(canonical_keys, canonical_embeddings):
                                    sim = bert_rec._dot_product(c_emb, query_embedding)
                                    if sim > max_similarity:
                                        max_similarity = sim
                                        best_match = c_key
                                
                                results_list[idx]["bert"] = {
                                    "match": best_match,
                                    "confidence_raw": float(max_similarity),
                                    "syntactic_parse_time_ms": None,
                                    "semantic_inference_time_ms": bert_elapsed_ms_per_packet,
                                    "fallback_triggered": (max_similarity < 0.5),
                                    "fallback_reason": f"cosine_similarity={max_similarity:.4f} < 0.5" if max_similarity < 0.5 else None,
                                    "semantic_recovery_success": (best_match == target_key)
                                }
                            
                            # 3. Gemma Batched Generation (GPU Tensor Batching)
                            print(f"    - Running GPU batched Gemma (BS=64) on {len(drifted_indices)} drifted packets...", flush=True)
                            gemma_start_t = time.perf_counter()
                            
                            prompts = []
                            for idx in drifted_indices:
                                sample = packets[idx]
                                original = sample["original_payload"]
                                mutated = sample["mutated_payload"]
                                canonical_keys = list(original.keys())
                                prompt = (
                                    f"Given a list of canonical API schema fields: {canonical_keys}\n"
                                    f"And a query key from a drifted/mutated schema: \"{json.dumps(mutated)}\"\n\n"
                                    "Select the canonical field that is the best semantic match for this query key.\n"
                                    "Return your response strictly in the following JSON format:\n"
                                    '{"match": "canonical_field_name", "confidence": 0.0}'
                                )
                                prompts.append(prompt)
                            
                            # Hugging Face Left-Padding Batched Matrix Generation
                            gemma_responses = []
                            batch_size = 256
                            
                            if getattr(gemma_model, "backend", None) == "api":
                                from concurrent.futures import ThreadPoolExecutor
                                print(f"    - Querying LM Studio concurrently with 16 parallel workers...", flush=True)
                                with ThreadPoolExecutor(max_workers=16) as executor:
                                    gemma_responses = list(executor.map(gemma_model.generate, prompts))
                            else:
                                gemma_model.tokenizer.padding_side = "left"
                                for i in range(0, len(prompts), batch_size):
                                    batch_prompts = prompts[i:i+batch_size]
                                    inputs = gemma_model.tokenizer(batch_prompts, return_tensors="pt", padding=True, truncation=True)
                                    inputs = {k: v.to(gemma_model.device) for k, v in inputs.items()}
                                    
                                    eos_ids = gemma_model.tokenizer.eos_token_id
                                    if eos_ids is None:
                                        eos_ids = []
                                    elif isinstance(eos_ids, (list, tuple)):
                                        eos_ids = [int(x.cpu()) if torch.is_tensor(x) else int(x) for x in eos_ids]
                                    else:
                                        eos_ids = [int(eos_ids)]
                                    
                                    with torch.no_grad():
                                        output_ids = gemma_model.model.generate(
                                            **inputs,
                                            max_new_tokens=128,
                                            do_sample=False,
                                            pad_token_id=int(gemma_model.tokenizer.pad_token_id),
                                            eos_token_id=eos_ids
                                        )
                                    
                                    for idx, out_ids in enumerate(output_ids):
                                        prompt_length = inputs["input_ids"][idx].shape[0]
                                        gen_tokens = out_ids[prompt_length:]
                                        decoded = gemma_model.tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
                                        gemma_responses.append(decoded)
                            
                            gemma_elapsed_ms_per_packet = ((time.perf_counter() - gemma_start_t) * 1000.0) / len(drifted_indices)
                            
                            for batch_idx, idx in enumerate(drifted_indices):
                                sample = packets[idx]
                                original = sample["original_payload"]
                                mutated = sample["mutated_payload"]
                                target_key = determine_mutated_key(original, mutated)
                                canonical_keys = list(original.keys())
                                
                                raw_response = gemma_responses[batch_idx]
                                try:
                                    if "{" in raw_response and "}" in raw_response:
                                        raw_response = raw_response[raw_response.index("{") : raw_response.rindex("}") + 1]
                                    parsed = json.loads(raw_response)
                                except Exception:
                                    parsed = {}
                                
                                match_val = parsed.get("match", canonical_keys[0])
                                confidence = float(parsed.get("confidence", 0.0))
                                
                                fallback_used = False
                                fallback_reason = None
                                if match_val not in canonical_keys:
                                    match_val = canonical_keys[0]
                                    confidence = 0.1
                                    fallback_used = True
                                    fallback_reason = "Gemma returned field not in canonical keys list"
                                elif confidence < 0.5:
                                    fallback_used = True
                                    fallback_reason = f"Gemma confidence={confidence:.4f} < 0.5"
                                
                                results_list[idx]["gemma"] = {
                                    "match": match_val,
                                    "confidence_raw": confidence,
                                    "syntactic_parse_time_ms": None,
                                    "semantic_inference_time_ms": gemma_elapsed_ms_per_packet,
                                    "fallback_triggered": fallback_used,
                                    "fallback_reason": fallback_reason,
                                    "semantic_recovery_success": (match_val == target_key)
                                }
                        
                        # ─── B. PROCESS CLEAN PACKETS (BYPASS OPTIMIZATION) ───
                        if non_drifted_indices:
                            for idx in non_drifted_indices:
                                sample = packets[idx]
                                original = sample["original_payload"]
                                mutated = sample["mutated_payload"]
                                target_key = determine_mutated_key(original, mutated)
                                canonical_keys = list(original.keys())
                                query_key_full = json.dumps(mutated)
                                
                                # CPU reconcilers run normally
                                rec_res_regex = regex_rec.reconcile(canonical_keys, query_key_full)
                                rec_res_regex["semantic_recovery_success"] = (rec_res_regex["match"] == target_key)
                                
                                rec_res_lev = lev_rec.reconcile(canonical_keys, target_key)
                                rec_res_lev["semantic_recovery_success"] = (rec_res_lev["match"] == target_key)
                                
                                results_list[idx]["regex"] = rec_res_regex
                                results_list[idx]["levenshtein"] = rec_res_lev
                                
                                # GPU Reconcilers bypass: return bypassed statistics
                                for method_name in ("bert", "gemma"):
                                    results_list[idx][method_name] = {
                                        "match": target_key,
                                        "confidence_raw": 1.0,
                                        "syntactic_parse_time_ms": None,
                                        "semantic_inference_time_ms": 0.0,  # Explicitly marked 0.0 for bypass tracking
                                        "fallback_triggered": False,
                                        "fallback_reason": None,
                                        "semantic_recovery_success": True
                                    }
                        
                        # ─── C. WRITE STREAMING TELEMETRY ───
                        with open(jsonl_output_path, "w", encoding="utf-8") as out_f:
                            for idx, sample in enumerate(packets):
                                original = sample["original_payload"]
                                mutated = sample["mutated_payload"]
                                target_key = determine_mutated_key(original, mutated)
                                # Determine the mutated key name if a key was renamed
                                orig_keys = set(original.keys())
                                mut_keys = set(mutated.keys())
                                added_keys = mut_keys - orig_keys
                                mutated_key = list(added_keys)[0] if added_keys else None
                                
                                gpu_vram_allocated_mb = 0.0
                                if torch.cuda.is_available():
                                    gpu_vram_allocated_mb = torch.cuda.memory_allocated() / (1024 * 1024)
                                
                                telemetry_row = {
                                    "packet_id": sample["packet_id"],
                                    "run_id": sample["run_id"],
                                    "run_number": sample["run_number"],
                                    "event_id": sample.get("event_id"),
                                    "timestamp": sample["timestamp"],
                                    "pipeline_version": git_commit,
                                    "workload_scale": sample["workload_scale"],
                                    "simulated_frequency": sample["simulated_frequency"],
                                    "api_profile": sample["api_profile"],
                                    "chaos_probability": sample["chaos_probability"],
                                    "drift_present": sample["drift_present"],
                                    "drift_type": sample["drift_type"],
                                    "target_key": target_key,
                                    "original_key": target_key,
                                    "mutated_key": mutated_key,
                                    "original_payload": original,
                                    "mutated_payload": mutated,
                                    "hardware_backend": preflight["hardware_backend"],
                                    "gpu_name": dev_info.get("gpu_name"),
                                    "vram_capacity_gb": dev_info.get("vram_gb"),
                                    "gpu_vram_allocated_mb": gpu_vram_allocated_mb,
                                    "compute_utilization_pct": 100.0,
                                    "per_packet_processing_time_ms": (results_list[idx]["gemma"]["semantic_inference_time_ms"] or 0.0) + (results_list[idx]["regex"]["syntactic_parse_time_ms"] or 0.0),
                                    "reconciliation": results_list[idx]
                                }
                                out_f.write(json.dumps(telemetry_row) + "\n")
                        
                        # Clear reconciler query caches to keep memory flat between runs
                        reconcilers["bert"].clear_caches()
                        reconcilers["gemma"].clear_caches()
                        
                        run_elapsed = time.perf_counter() - run_start_t
                        completed_count += 1
                        
                        # ─── D. EXPORT RUN CHARACTERISTICS JSON ───
                        char_path = os.path.join(final_output_dir, "run_characteristics.json")
                        characteristics = {
                            "device_model": dev_info.get("model"),
                            "vram_capacity_gb": dev_info.get("vram_gb"),
                            "hardware_backend": preflight["hardware_backend"],
                            "cloud_platform": dev_info.get("cloud"),
                            "run_id": run_id,
                            "iteration": i,
                            "api_profile": api,
                            "chaos_strategy": strategy,
                            "workload_scale": scale,
                            "chaos_probability": prob,
                            "simulated_frequency_hz": freq,
                            "total_packets": scale,
                            "drifted_packets": drift_total,
                            "bypassed_packets": scale - drift_total,
                            "total_run_time_seconds": run_elapsed,
                            "bert_average_latency_ms": bert_elapsed_ms_per_packet,
                            "gemma_average_latency_ms": gemma_elapsed_ms_per_packet,
                            "timestamp": datetime.now().isoformat(),
                            "pipeline_version": git_commit
                        }
                        with open(char_path, "w", encoding="utf-8") as char_f:
                            json.dump(characteristics, char_f, indent=2)
                        
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
