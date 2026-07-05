#!/usr/bin/env python3
"""
run_gpu_scalability_sweep.py — Measures the scalability of the LLM-tier reconciler 
(Gemma / Nemotron) as it scales from 1 to 8 GPUs. 

Measures model load times, inference latencies, memory footprint, and speedup margins.
"""

import os
import sys

# --- Mock amdsmi to work around PyTorch/ROCm packaging bug ---
from types import ModuleType
if 'amdsmi' not in sys.modules:
    dummy = ModuleType('amdsmi')
    dummy.AmdSmiException = Exception
    dummy.amdsmi_init = lambda: None
    sys.modules['amdsmi'] = dummy
import time
import json
import gc

def main():
    # Pick the model to evaluate (Gemma-4 or Nemotron)
    model_id = os.environ.get("HF_MODEL_ID", "google/gemma-4-E4B-it")
    print(f"=== GPU Scalability Sweep ===")
    print(f"Model: {model_id}")
    print(f"Evaluating GPU counts: 1 to 8\n")

    # Sample F1 telemetry schema pairs for inference evaluation
    original_schema = {
        "driver_number": 44,
        "speed": 298.4,
        "rpm": 11840,
        "gear": 7,
        "throttle": 100.0,
        "brake": 0.0,
        "drs": 12,
        "date": "2026-07-05T14:15:30Z"
    }

    drifted_schema = {
        "driver_id": 44,
        "velocity_kmh": 298.4,
        "engine_rotations": 11840,
        "selected_gear": 7,
        "gas_pedal_pct": 100.0,
        "brake_pressure_pct": 0.0,
        "drs_status": 12,
        "timestamp_utc": "2026-07-05T14:15:30Z"
    }

    results = []

    # Iterate over GPU counts from 1 to 8
    for gpu_count in range(1, 9):
        print(f"--- Benchmarking with {gpu_count} GPU(s) ---")
        
        # Set visible devices
        visible_gpus = ",".join(str(i) for i in range(gpu_count))
        os.environ["CUDA_VISIBLE_DEVICES"] = visible_gpus
        
        # Force PyTorch and ROCm to only see the specified device subset
        import torch
        torch.cuda.empty_cache()
        
        load_start = time.perf_counter()
        
        # Load the model using our LLMManager
        # Using 4bit quantization to fit easily in memory and speed up tests
        from src.inference.llm_manager import LLMManager
        manager = LLMManager(
            model_id=model_id,
            device="cuda",
            load_in_4bit=True,
            lazy=False
        )
        
        load_time = time.perf_counter() - load_start
        print(f"  Model loaded onto {gpu_count} GPU(s) in {load_time:.2f}s")
        
        # Run 5 warm-up and evaluation iterations to measure stable inference latency
        infer_times = []
        messages = [{
            "role": "user",
            "content": (
                f"Map original fields to drifted fields.\n"
                f"Original: {json.dumps(original_schema)}\n"
                f"Drifted: {json.dumps(drifted_schema)}\n"
                f"Output ONLY: {{\"original\": \"drifted\"}}"
            )
        }]

        print("  Evaluating inference latency (5 repeats)...")
        for i in range(5):
            t_start = time.perf_counter()
            response = manager.generate_response(messages, max_new_tokens=128)
            t_eval = time.perf_counter() - t_start
            infer_times.append(t_eval)
            print(f"    Run {i+1}: {t_eval*1000:.1f} ms")

        avg_latency_ms = float(np.mean(infer_times) * 1000) if 'np' in sys.modules else float(sum(infer_times)/len(infer_times) * 1000)
        std_latency_ms = float(np.std(infer_times) * 1000) if 'np' in sys.modules else 0.0

        # Collect VRAM allocation across active devices
        vram_allocated_mb = 0
        try:
            for idx in range(gpu_count):
                vram_allocated_mb += torch.cuda.memory_allocated(idx) / (1024 * 1024)
        except Exception:
            pass

        results.append({
            "gpu_count": gpu_count,
            "load_time_sec": load_time,
            "latency_mean_ms": avg_latency_ms,
            "latency_std_ms": std_latency_ms,
            "vram_total_mb": vram_allocated_mb
        })

        # Unload and clean VRAM
        manager.unload()
        del manager
        gc.collect()
        torch.cuda.empty_cache()
        print(f"  VRAM released. Average Latency: {avg_latency_ms:.2f} ms\n")

    # Compute Speedups relative to 1 GPU baseline
    baseline_latency = results[0]["latency_mean_ms"]
    for res in results:
        res["speedup"] = baseline_latency / res["latency_mean_ms"]

    # Save to CSV
    reports_dir = "data/reports/live_f1"
    os.makedirs(reports_dir, exist_ok=True)
    summary_path = os.path.join(reports_dir, "gpu_scalability_results.csv")
    
    with open(summary_path, "w") as f:
        f.write("gpu_count,load_time_sec,latency_mean_ms,latency_std_ms,vram_total_mb,speedup\n")
        for res in results:
            f.write(f"{res['gpu_count']},{res['load_time_sec']:.3f},{res['latency_mean_ms']:.2f},"
                    f"{res['latency_std_ms']:.2f},{res['vram_total_mb']:.1f},{res['speedup']:.2f}\n")

    print("=" * 60)
    print("  SCALABILITY SWEEP COMPLETE")
    print("=" * 60)
    print(f"Results saved to: {summary_path}\n")

    # Print summary table
    print("| GPUs | Load Time (s) | Packet Latency (ms) | Speedup | Total VRAM (MB) |")
    print("| :---: | :---: | :---: | :---: | :---: |")
    for res in results:
        print(f"| {res['gpu_count']} | {res['load_time_sec']:.2f}s | {res['latency_mean_ms']:.1f} ± {res['latency_std_ms']:.1f} | {res['speedup']:.2f}x | {res['vram_total_mb']:.1f} |")
    print("=" * 60)

if __name__ == "__main__":
    # Ensure numpy is imported if available
    try:
        import numpy as np
    except ImportError:
        pass
    main()
