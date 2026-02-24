#!/usr/bin/env python3
"""Profile the GPUSemanticReconciler embedding step with CUDA traces.
Generates `outputs/bert_trace.json` and prints a profiler summary.
"""
from __future__ import annotations

import os
import time
import torch
from torch.profiler import profile, record_function, ProfilerActivity

# Import the reconciler and canonical schema
from tools.cadillac_gpu_stress_test import GPUSemanticReconciler
from modules.translator import CANONICAL_SENSORS

OUT_DIR = "outputs"
os.makedirs(OUT_DIR, exist_ok=True)

BATCH_SIZE = 128
WARMUP = 8
ITER = 32

# Build a representative batch of sensor names (some variants to stimulate BERT)
base = CANONICAL_SENSORS
variants = [s for s in base]
variants += [s + "_v2" for s in base]
variants += [s.replace("_", "") for s in base]
batch = [variants[i % len(variants)] for i in range(BATCH_SIZE)]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Device for profiling:", device)

print("Initializing GPUSemanticReconciler (loads model) — this may take a moment...")
reconciler = GPUSemanticReconciler(schema=CANONICAL_SENSORS, device=device)

print(f"Warmup: {WARMUP} iterations; Profile iterations: {ITER}; batch_size={BATCH_SIZE}")

with profile(
    activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
    record_shapes=True,
    profile_memory=True,
    with_stack=False,
) as prof:
    # Warmup runs (not recorded in profiler timings of interest)
    for _ in range(WARMUP):
        _ = reconciler.resolve_batch(batch)
    # Profiled iterations
    with record_function("bert_resolve_loop"):
        for _ in range(ITER):
            _ = reconciler.resolve_batch(batch)

    if device.type == "cuda":
        torch.cuda.synchronize()

print("\nProfiler summary (top CUDA time):")
print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=30))

trace_path = os.path.join(OUT_DIR, "bert_trace.json")
print(f"Exporting Chrome trace to: {trace_path}")
prof.export_chrome_trace(trace_path)
print("Done.")
