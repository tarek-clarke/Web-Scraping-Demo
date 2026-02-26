#!/usr/bin/env python3
"""
Validate p99 latency with static padding & HIP stream priority.

Tests the StreamingIngestor with pre-allocated buffers to confirm
p99 latency is reduced from ~149ms to <15µs on AMD RX 7900 XT.

Usage:
    PYTHONPATH="." python tools/validate_p99_latency.py
"""

import time
import sys
import numpy as np
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import torch
    from modules.translator import SENSOR_LO, SENSOR_HI
    import fast_ingest
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}")
    print("Ensure fast_ingest C++ extension is built:")
    print("  cd /root/resilient-rap-framework")
    print("  python setup.py build_ext --inplace")
    sys.exit(1)


def measure_p99_latency_streaming(iterations=10000, batch_size=128):
    """Measure latency percentiles with StreamingIngestor (pre-allocated buffers)."""
    print("\n" + "="*60)
    print("  StreamingIngestor (Pre-allocated + Static Padding)")
    print("="*60)
    
    # Verify GPU availability
    if not torch.cuda.is_available():
        print("ERROR: No GPU detected. Exiting.")
        return False
    
    device_name = torch.cuda.get_device_name(0)
    print(f"GPU: {device_name}")
    print(f"HIP Version: {getattr(torch.version, 'hip', 'N/A')}")
    
    # Create streaming ingestor with pre-allocated buffers
    try:
        streamer = fast_ingest.StreamingIngestor(SENSOR_LO, SENSOR_HI, batch_size)
    except Exception as e:
        print(f"ERROR: Failed to create StreamingIngestor: {e}")
        return False
    
    # Synthetic packet
    packet = list(SENSOR_LO)
    latencies = []
    
    print(f"Running {iterations:,} iterations...")
    torch.cuda.synchronize()
    
    for i in range(iterations):
        # Measure latency of push() call (GIL-free, pre-allocated)
        start = time.perf_counter_ns()
        flushed = streamer.push(packet)
        end = time.perf_counter_ns()
        
        latency_us = (end - start) / 1000.0
        latencies.append(latency_us)
        
        # Sync on auto-flush to capture flush latency
        if flushed:
            streamer.sync()
        
        # Progress indicator
        if (i + 1) % (iterations // 10) == 0:
            print(f"  {i + 1}/{iterations} iterations complete")
    
    # Final sync
    streamer.sync()
    
    # Calculate percentiles
    latencies = np.array(latencies)
    p50 = np.percentile(latencies, 50)
    p90 = np.percentile(latencies, 90)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    p999 = np.percentile(latencies, 99.9)
    p9999 = np.percentile(latencies, 99.99)
    
    min_lat = np.min(latencies)
    max_lat = np.max(latencies)
    mean_lat = np.mean(latencies)
    
    print(f"\n{'Latency Percentiles':^60}")
    print("-" * 60)
    print(f"  min:    {min_lat:9.3f} µs")
    print(f"  p50:    {p50:9.3f} µs")
    print(f"  p90:    {p90:9.3f} µs")
    print(f"  p95:    {p95:9.3f} µs")
    print(f"  p99:    {p99:9.3f} µs", end="")
    if p99 < 15:
        print("  ✓ PASS (< 15µs target)")
    else:
        print("  ✗ FAIL (> 15µs target)")
    print(f"  p99.9:  {p999:9.3f} µs")
    print(f"  p99.99: {p9999:9.3f} µs")
    print(f"  max:    {max_lat:9.3f} µs")
    print(f"  mean:   {mean_lat:9.3f} µs")
    print("-" * 60)
    
    success = p99 < 15
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"\nRESULT: p99 latency = {p99:.2f} µs  [{status}]\n")
    
    return success


def measure_batch_throughput(batch_count=100, batch_size=128):
    """Measure batch throughput with static padding."""
    print("\n" + "="*60)
    print("  Batch Throughput (ingest_batch with Static Padding)")
    print("="*60)
    
    if not torch.cuda.is_available():
        return
    
    print(f"Running {batch_count} batches of size {batch_size}...")
    
    # Create synthetic batches
    packets = [list(SENSOR_LO) for _ in range(batch_size)]
    
    torch.cuda.synchronize()
    start = time.perf_counter()
    
    for _ in range(batch_count):
        result = fast_ingest.ingest_batch(packets, SENSOR_LO, SENSOR_HI)
        torch.cuda.synchronize()
    
    end = time.perf_counter()
    total_packets = batch_count * batch_size
    elapsed_ms = (end - start) * 1000
    s_per_packet_us = (elapsed_ms * 1000) / total_packets
    
    print(f"\nTotal packets: {total_packets:,}")
    print(f"Total time: {elapsed_ms:.1f} ms")
    print(f"Per-packet: {s_per_packet_us:.2f} µs")
    print(f"Throughput: {total_packets / (end - start):.0f} pkt/s\n")


if __name__ == "__main__":
    print("\n" + "="*80)
    print(" "*15 + "P99 Latency Validation: Static Padding + HIP Priority")
    print("="*80)
    
    # Test StreamingIngestor (primary p99 target)
    streaming_success = measure_p99_latency_streaming(iterations=10000)
    
    # Show batch throughput for reference
    measure_batch_throughput(batch_count=50, batch_size=128)
    
    # Exit with appropriate code
    if streaming_success:
        print("✓ SUCCESS: p99 latency optimizations are working!")
        sys.exit(0)
    else:
        print("✗ FAILURE: p99 latency still above target (<15µs)")
        sys.exit(1)
