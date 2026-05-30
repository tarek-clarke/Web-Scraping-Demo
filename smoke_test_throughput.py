import os
import sys
import time
import random

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from semantic_benchmark.model_loaders import StrictGemmaModel, StrictBERTModel
from semantic_benchmark.reconcilers import GemmaReconciler, RegexReconciler, BERTReconciler, LevenshteinReconciler

def main():
    print("================================================================================")
    print(" HARDWARE THROUGHPUT SMOKE TEST (7900XT)")
    print("================================================================================")
    
    print("[*] Loading Reconcilers...")
    # Load fast reconcilers
    regex = RegexReconciler()
    lev = LevenshteinReconciler()
    
    # Load heavy reconcilers
    print("    - Initializing BERT...")
    bert_model = StrictBERTModel(require_local=True)
    bert = BERTReconciler(bert_model)
    
    print("    - Initializing Gemma...")
    gemma_model = StrictGemmaModel(require_local=True)
    gemma = GemmaReconciler(gemma_model)
    
    canonical_keys = ["price", "cost", "amount", "monetary", "usd", "val"]
    pristine_query = "price"
    drifted_query = "prc"
    
    scale = 1000 # Test with 1,000 packets for speed
    chaos_prob = 0.05
    
    print(f"\n[*] Simulating {scale} packet stream with {chaos_prob*100}% chaos...")
    
    start_time = time.time()
    
    llm_invocations = 0
    fast_invocations = 0
    
    for _ in range(scale):
        if random.random() < chaos_prob:
            # Drifted packet: LLM is invoked
            query = drifted_query
            llm_invocations += 1
            # Simulate pipeline cascading
            res = gemma.reconcile(canonical_keys, query)
        else:
            # Pristine packet: fast path
            query = pristine_query
            fast_invocations += 1
            res = regex.reconcile(canonical_keys, query)
            
    end_time = time.time()
    elapsed = end_time - start_time
    
    print("\n================================================================================")
    print(" SMOKE TEST RESULTS")
    print("================================================================================")
    print(f"Total time for {scale} packets: {elapsed:.2f} seconds")
    print(f"Fast path invocations : {fast_invocations}")
    print(f"LLM path invocations  : {llm_invocations}")
    
    if elapsed > 0:
        packets_per_sec = scale / elapsed
        print(f"Throughput: {packets_per_sec:.2f} packets/second")
    else:
        packets_per_sec = 0.0
        
    print("\n[*] Extrapolating matrix execution time...")
    # There are 4320 total runs. 2160 are 1M scale, 2160 are 10k scale.
    # We are isolating reconcilers, so ONLY 1/4th of runs (1080) use Gemma.
    # Out of those, 1M scale is 540 runs. 10k scale is 540 runs.
    
    # Time for 1M packets using Gemma (at 5% chaos):
    # elapsed for 1000 packets * 1000 = time for 1M packets.
    time_1m = (elapsed / scale) * 1_000_000 if packets_per_sec > 0 else 0
    
    print(f"Estimated time per 1M packet run (at 5% chaos): {time_1m/3600:.2f} hours")
    print(f"Total time for all 540 Gemma 1M runs: {(time_1m * 540) / 86400:.2f} days")
    print("================================================================================\n")

if __name__ == "__main__":
    main()
