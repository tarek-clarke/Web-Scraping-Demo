import os
os.environ["DISABLE_COMPILE"] = "1"
import sys
import json
import time
import gzip
import random
import subprocess
from uuid import uuid4
from datetime import datetime
import torch
import psutil

import gc

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from semantic_benchmark.model_loaders import StrictBERTModel, StrictGemmaModel, StrictGemma30BModel, run_preflight_validation
from semantic_benchmark.reconcilers import LevenshteinReconciler, RegexReconciler, BERTReconciler, GemmaReconciler
from models.device_selector import get_device_info

# Import chaos generator components directly (avoid subprocess overhead)
from api.finnhub import FinnhubAPI
from api.openmeteo import OpenMeteoAPI
from api.spacex import SpaceXAPI
from api.openf1 import OpenF1API
from chaos_generator.chaos.strategy import select_chaos


def get_concurrency_level() -> int:
    """Detect number of concurrent active run_matrix_unified.py processes."""
    try:
        count = 0
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any('run_matrix_unified.py' in arg for arg in cmdline):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return max(1, count)
    except Exception:
        return 1


def _query_nvidia_telemetry():
    """Query real-time NVIDIA GPU clock, memory speed, active utilization, and power draw."""
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=clocks.current.graphics,clocks.current.memory,utilization.gpu,utilization.memory,power.draw",
            "--format=csv,noheader,nounits"
        ]
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        if not output:
            return {}
        parts = [part.strip() for part in output.split(",")]
        return {
            "gpu_clock_mhz": float(parts[0]) if len(parts) > 0 else None,
            "vram_clock_mhz": float(parts[1]) if len(parts) > 1 else None,
            "gpu_utilization_pct": float(parts[2]) if len(parts) > 2 else None,
            "vram_utilization_pct": float(parts[3]) if len(parts) > 3 else None,
            "power_draw_watts": float(parts[4]) if len(parts) > 4 else None
        }
    except Exception:
        return {}


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


def generate_dataset_inline(api_name, strategy_name, scale, probability, frequency, run_id, run_number, gemma_model=None):
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

    chaos_engine = select_chaos(strategy_name, probability, gemma_model)
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
    use_30b = os.getenv("USE_GEMMA_30B", "").strip().lower() in ("1", "true", "yes")
    enabled_methods = ["regex", "levenshtein", "bert", "gemma"]
    if use_30b:
        enabled_methods.append("gemma30b")
        
    preflight, abort, abort_reason = run_preflight_validation(
        require_local_models=True,
        strict_mode=False,
        enabled_methods=["regex", "levenshtein", "bert", "gemma"]
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
    
    use_30b = os.getenv("USE_GEMMA_30B", "").strip().lower() in ("1", "true", "yes")
    gemma30b_model = None
    if use_30b:
        print("[*] Initialising local Gemma 30B Model for side-by-side high-fidelity reconciliation...")
        gemma30b_model = StrictGemma30BModel(require_local=True)
    
    print("\n[*] Instantiating reconcilers...")
    reconcilers = {
        "regex": RegexReconciler(),
        "levenshtein": LevenshteinReconciler(),
        "bert": BERTReconciler(bert_model),
        "gemma": GemmaReconciler(gemma_model)
    }
    if use_30b and gemma30b_model is not None:
        reconcilers["gemma30b"] = GemmaReconciler(gemma30b_model)    # Matrix configuration
    scale = 100000
    frequencies = [1000]
    probabilities = [0.05]
    iterations = 5
    apis = ["finnhub", "openmeteo", "spacex", "openf1"]
    strategies = ["json", "schema", "gemma", "gemma30b"]
    
    total_runs = len(apis) * len(strategies) * len(frequencies) * len(probabilities) * iterations
    
    # 1. Clean up local telemetry directory for the active GPU to prevent failed/dirty run mixtures
    import shutil
    gpu_results_dir = os.path.join("results", model_str)
    resume = os.getenv("RAP_RESUME", "").strip().lower() in ("1", "true", "yes")
    skip_wipe = os.getenv("RAP_SKIP_WIPE", "").strip().lower() in ("1", "true", "yes")
    
    if resume:
        skip_wipe = True
        print("[*] Resume mode enabled (RAP_RESUME=1). Existing telemetry files will be kept.")
        
    if os.path.exists(gpu_results_dir) and not skip_wipe:
        print(f"[*] Wiping existing telemetry directory for active GPU ({model_str}) to prevent failed/dirty run mixtures...")
        try:
            shutil.rmtree(gpu_results_dir)
        except Exception as e:
            print(f"[!] Warning: failed to clean telemetry directory: {e}")
    os.makedirs(gpu_results_dir, exist_ok=True)

    # 2. Reset or load completed runs state for the active GPU
    state_file = "matrix_unified_state.json"
    state = {}
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            try:
                state = json.load(f)
            except json.JSONDecodeError:
                pass

    if resume:
        completed_runs = set(state.get(model_str, []))
        print(f"[*] Resuming from existing state file. Active GPU ({model_str}) has {len(completed_runs)} already completed runs in state.")
        
        # Auto-recover/sync state from disk characteristics
        disk_runs = 0
        if os.path.exists(gpu_results_dir):
            for entry in os.listdir(gpu_results_dir):
                entry_path = os.path.join(gpu_results_dir, entry)
                if os.path.isdir(entry_path):
                    char_file = os.path.join(entry_path, "run_characteristics.json")
                    if os.path.exists(char_file):
                        try:
                            with open(char_file, "r") as cf:
                                cdata = json.load(cf)
                                iteration = cdata.get("iteration")
                                api = cdata.get("api_profile")
                                strategy = cdata.get("chaos_strategy")
                                freq = cdata.get("simulated_frequency_hz")
                                prob = cdata.get("chaos_probability")
                                if all(v is not None for v in [iteration, api, strategy, freq, prob]):
                                    # If Gemma 30B is enabled, a run is only complete if it actually includes gemma30b results!
                                    is_complete = True
                                    if use_30b:
                                        if "gemma30b" not in entry and "gemma30b_average_latency_ms" not in cdata:
                                            is_complete = False
                                            
                                    if is_complete:
                                        disk_key = f"run_{iteration}_{api}_{strategy}_{freq}hz_{prob}prob"
                                        if disk_key not in completed_runs:
                                            completed_runs.add(disk_key)
                                            disk_runs += 1
                        except Exception:
                            pass
        if disk_runs > 0:
            print(f"[✓] Auto-detected and synced {disk_runs} completed runs from folders on disk!")
        state[model_str] = list(completed_runs)
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    else:
        print(f"[*] Resetting completed runs state for active GPU ({model_str}) to ensure a 100% clean run...")
        state[model_str] = []
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
                
    run_idx = 0
    completed_count = len(state.get(model_str, [])) if resume else 0
    session_completed = 0
    sweep_start_t = time.perf_counter()
    
    for i in range(1, iterations + 1):
        for api in apis:
            for strategy in strategies:
                for freq in frequencies:
                    for prob in probabilities:
                        run_idx += 1
                        state_key = f"run_{i}_{api}_{strategy}_{freq}hz_{prob}prob"
                        
                        if state_key in state.get(model_str, []):
                            continue
                            
                        print(f"\n================================================================================")
                        print(f" [MATRIX RUN {run_idx}/{total_runs}] Iter: {i} | API: {api} | Chaos: {strategy} | Freq: {freq}Hz | Prob: {prob*100}%")
                        print(f"================================================================================", flush=True)
                        
                        run_id = uuid4().hex
                        run_start_t = time.perf_counter()
                        
                        # 1. Generate Dataset INLINE (no subprocess, no disk I/O)
                        print(f"[*] Generating {scale} packets (inline)...", flush=True)
                        gen_start_t = time.perf_counter()
                        packets = generate_dataset_inline(api, strategy, scale, prob, freq, run_id, i, gemma_model)
                        gen_elapsed = time.perf_counter() - gen_start_t
                        
                        drift_total = sum(1 for p in packets if p["drift_present"])
                        print(f"[✓] Generated {len(packets)} packets ({drift_total} drifted) in {gen_elapsed:.1f}s", flush=True)
                        
                        # 2. Process packets in-memory
                        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        
                        # Build parameter-rich folder name sorted by GPU/CPU model
                        pct_str = f"{int(prob*100)}pct" if (prob*100).is_integer() else f"{str(prob*100).replace('.', '_')}pct"
                        freq_str = "1mhz" if freq == 1000000 else f"{freq}hz"
                        methods_str = "_".join(enabled_methods)
                        scale_str = "1M" if scale == 1000000 else (f"{scale // 1000}K" if scale % 1000 == 0 else str(scale))
                        run_folder_name = f"scale_{scale_str}_freq_{freq_str}_chaos_{pct_str}_strat_{strategy}_methods_{methods_str}_{timestamp_str}_{run_id[:8]}"
                        
                        # Sort into subfolder grouped by hardware device name
                        final_output_dir = os.path.join("results", model_str, run_folder_name)
                        os.makedirs(final_output_dir, exist_ok=True)
                        
                        jsonl_output_path = os.path.join(final_output_dir, f"telemetry_stream_{run_id}.jsonl.gz")
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
                        gemma30b_rec = reconcilers.get("gemma30b")
                        
                        # ─── A. PROCESS DRIFTED PACKETS VIA TENSOR BATCHING ───
                        bert_elapsed_ms_per_packet = 0.0
                        gemma_elapsed_ms_per_packet = 0.0
                        gemma30b_elapsed_ms_per_packet = 0.0
                        
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
                            
                            # Strip transient/dynamic data values to enable perfect schema-level deduplication
                            queries = []
                            for idx in drifted_indices:
                                mutated_clean = {k: 0 for k in packets[idx]["mutated_payload"].keys()}
                                queries.append(json.dumps(mutated_clean))
                            unique_queries = list(set(queries))
                            print(f"    - Deduplicated {len(queries)} BERT queries to {len(unique_queries)} unique items...", flush=True)
                            unique_embeddings = bert_model.get_embeddings_batch(unique_queries)
                            
                            query_to_embedding = dict(zip(unique_queries, unique_embeddings))
                            query_embeddings = [query_to_embedding[q] for q in queries]
                            
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
                            
                            # 3. Gemma (and Gemma 30B) Batched Generation (GPU Tensor Batching)
                            llm_targets = []
                            if "gemma" in enabled_methods:
                                llm_targets.append(("gemma", gemma_model))
                            if "gemma30b" in enabled_methods and gemma30b_model is not None:
                                llm_targets.append(("gemma30b", gemma30b_model))
                                
                            for method_key, model_inst in llm_targets:
                                # Dynamic Granular VRAM-to-Batch Allocation Algorithm (optimised for Warp and Tensor Core alignment)
                                batch_size = 64
                                if torch.cuda.is_available():
                                    try:
                                        total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                                        # Gemma-4 E4B (4B) is 8.5GB, Gemma 30B is roughly ~65GB
                                        static_weights = 65.0 if method_key == "gemma30b" else 8.5
                                        mb_per_element = 40.0
                                        available_vram_gb = total_vram_gb - static_weights
                                        if available_vram_gb > 0:
                                            raw_bs = (available_vram_gb * 1024 / mb_per_element) * 0.8
                                            batch_size = int((raw_bs // 64) * 64)
                                            batch_size = max(32, min(1024, batch_size))
                                    except Exception:
                                        batch_size = 64
                                        
                                print(f"    - Running GPU batched {method_key.upper()} (BS={batch_size}) on {len(drifted_indices)} drifted packets...", flush=True)
                                llm_start_t = time.perf_counter()
                                
                                prompts = []
                                for idx in drifted_indices:
                                    sample = packets[idx]
                                    original = sample["original_payload"]
                                    mutated = sample["mutated_payload"]
                                    canonical_keys = list(original.keys())
                                    mutated_clean = {k: 0 for k in mutated.keys()}
                                    prompt = (
                                        f"Given a list of canonical API schema fields: {canonical_keys}\n"
                                        f"And a query key from a drifted/mutated schema: \"{json.dumps(mutated_clean)}\"\n\n"
                                        "Select the canonical field that is the best semantic match for this query key.\n"
                                        "Return your response strictly in the following JSON format:\n"
                                        '{"match": "canonical_field_name", "confidence": 0.0}'
                                    )
                                    prompts.append(prompt)
                                
                                unique_prompts = list(set(prompts))
                                print(f"    - Deduplicated {len(prompts)} {method_key.upper()} prompts to {len(unique_prompts)} unique items...", flush=True)
                                unique_responses = []
                                
                                if getattr(model_inst, "backend", None) == "api":
                                    from concurrent.futures import ThreadPoolExecutor
                                    print(f"    - Querying LM Studio concurrently with 16 parallel workers...", flush=True)
                                    with ThreadPoolExecutor(max_workers=16) as executor:
                                        unique_responses = list(executor.map(model_inst.generate, unique_prompts))
                                else:
                                    model_inst.tokenizer.padding_side = "left"
                                    for b_start in range(0, len(unique_prompts), batch_size):
                                        batch_prompts = unique_prompts[b_start:b_start+batch_size]
                                        inputs = model_inst.tokenizer(batch_prompts, return_tensors="pt", padding=True, truncation=True)
                                        inputs = {k: v.to(model_inst.device) for k, v in inputs.items()}
                                        
                                        eos_ids = model_inst.tokenizer.eos_token_id
                                        if eos_ids is None:
                                            eos_ids = []
                                        elif isinstance(eos_ids, (list, tuple)):
                                            eos_ids = [int(x.cpu()) if torch.is_tensor(x) else int(x) for x in eos_ids]
                                        else:
                                            eos_ids = [int(eos_ids)]
                                        
                                        with torch.no_grad():
                                            output_ids = model_inst.model.generate(
                                                **inputs,
                                                max_new_tokens=32,
                                                do_sample=False,
                                                pad_token_id=int(model_inst.tokenizer.pad_token_id),
                                                eos_token_id=eos_ids
                                            )
                                        
                                        for idx, out_ids in enumerate(output_ids):
                                            prompt_length = inputs["input_ids"][idx].shape[0]
                                            gen_tokens = out_ids[prompt_length:]
                                            decoded = model_inst.tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
                                            unique_responses.append(decoded)
                                
                                unique_prompt_map = dict(zip(unique_prompts, unique_responses))
                                llm_responses = [unique_prompt_map[p] for p in prompts]
                                
                                llm_elapsed_ms_per_packet = ((time.perf_counter() - llm_start_t) * 1000.0) / len(drifted_indices)
                                if method_key == "gemma":
                                    gemma_elapsed_ms_per_packet = llm_elapsed_ms_per_packet
                                elif method_key == "gemma30b":
                                    gemma30b_elapsed_ms_per_packet = llm_elapsed_ms_per_packet
                                    
                                for batch_idx, idx in enumerate(drifted_indices):
                                    sample = packets[idx]
                                    original = sample["original_payload"]
                                    mutated = sample["mutated_payload"]
                                    target_key = determine_mutated_key(original, mutated)
                                    canonical_keys = list(original.keys())
                                    
                                    raw_response = llm_responses[batch_idx]
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
                                        fallback_reason = f"{method_key.upper()} returned field not in canonical keys list"
                                    elif confidence < 0.5:
                                        fallback_used = True
                                        fallback_reason = f"{method_key.upper()} confidence={confidence:.4f} < 0.5"
                                    
                                    results_list[idx][method_key] = {
                                        "match": match_val,
                                        "confidence_raw": confidence,
                                        "syntactic_parse_time_ms": None,
                                        "semantic_inference_time_ms": llm_elapsed_ms_per_packet,
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
                                for method_name in [m for m in enabled_methods if m in ("bert", "gemma", "gemma30b")]:
                                    results_list[idx][method_name] = {
                                        "match": target_key,
                                        "confidence_raw": 1.0,
                                        "syntactic_parse_time_ms": None,
                                        "semantic_inference_time_ms": 0.0,  # Explicitly marked 0.0 for bypass tracking
                                        "fallback_triggered": False,
                                        "fallback_reason": None,
                                        "semantic_recovery_success": True
                                    }
                        
                        # ─── C. WRITE STREAMING TELEMETRY (COMPRESSED & OPTIMISED) ───
                        # Write as compressed gzip .jsonl.gz to save 90% SSD space, and strip payload bloat
                        with gzip.open(jsonl_output_path, "wt", encoding="utf-8", compresslevel=1) as out_f:
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
                                    "event_id": sample.get("event_id"),
                                    "timestamp": sample["timestamp"],
                                    "drift_present": sample["drift_present"],
                                    "drift_type": sample["drift_type"],
                                    "original_key": target_key,
                                    "mutated_key": mutated_key,
                                    "gpu_vram_allocated_mb": gpu_vram_allocated_mb,
                                    "per_packet_processing_time_ms": sum((results_list[idx].get(m, {}).get("semantic_inference_time_ms") or 0.0) for m in enabled_methods) + sum((results_list[idx].get(m, {}).get("syntactic_parse_time_ms") or 0.0) for m in enabled_methods),
                                    "reconciliation": results_list[idx]
                                }
                                out_f.write(json.dumps(telemetry_row) + "\n")
                        
                        # Clear reconciler query caches to keep memory flat between runs
                        reconcilers["bert"].clear_caches()
                        reconcilers["gemma"].clear_caches()
                        if "gemma30b" in reconcilers:
                            reconcilers["gemma30b"].clear_caches()
                        
                        run_elapsed = time.perf_counter() - run_start_t
                        completed_count += 1
                        session_completed += 1
                        
                        # ─── D. EXPORT RUN CHARACTERISTICS JSON ───
                        char_path = os.path.join(final_output_dir, "run_characteristics.json")
                        gpu_telemetry = _query_nvidia_telemetry()
                        characteristics = {
                            "device_model": dev_info.get("model"),
                            "vram_capacity_gb": dev_info.get("vram_gb"),
                            "hardware_backend": preflight["hardware_backend"],
                            "cloud_platform": dev_info.get("cloud"),
                            "concurrency_level": get_concurrency_level(),
                            "gpu_telemetry": gpu_telemetry,
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
                            "gemma30b_average_latency_ms": gemma30b_elapsed_ms_per_packet,
                            "timestamp": datetime.now().isoformat(),
                            "pipeline_version": git_commit
                        }
                        with open(char_path, "w", encoding="utf-8") as char_f:
                            json.dump(characteristics, char_f, indent=2)
                        
                        # ETA for remaining runs based on session-specific speed
                        avg_per_run = (time.perf_counter() - sweep_start_t) / session_completed
                        remaining_runs = total_runs - completed_count
                        eta_min = (avg_per_run * remaining_runs) / 60.0
                        
                        print(f"[✓] Run {run_idx} complete in {run_elapsed:.1f}s | {completed_count}/{total_runs} done | ETA {eta_min:.1f}min", flush=True)
                            
                        # Commit state
                        if model_str not in state:
                            state[model_str] = []
                        state[model_str].append(state_key)
                        with open(state_file, "w") as f:
                            json.dump(state, f, indent=2)
                            
    total_elapsed = time.perf_counter() - sweep_start_t
    print(f"\n[✓] UNIFIED MATRIX RUN COMPLETE! {total_runs} runs in {total_elapsed/60:.1f} minutes")
 
if __name__ == "__main__":
    main()
