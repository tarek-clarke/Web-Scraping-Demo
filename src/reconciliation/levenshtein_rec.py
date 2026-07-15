import time
from typing import Dict, List, Tuple
import Levenshtein
import multiprocessing

def _reconcile_single_pair(args: Tuple[Dict, Dict]) -> Dict:
    original, drifted = args
    if isinstance(original, list):
        original = {str(i): v for i, v in enumerate(original)}
    elif not isinstance(original, dict):
        original = {}
    if isinstance(drifted, list):
        drifted = {str(i): v for i, v in enumerate(drifted)}
    elif not isinstance(drifted, dict):
        drifted = {}
    start = time.perf_counter()
    
    orig_keys = set(original.keys())
    drift_keys = set(drifted.keys())
    
    mapped = []
    unmapped = []
    total_score = 0.0
    
    for ok in orig_keys:
        best_match = None
        best_dist = float('inf')
        
        for dk in drift_keys:
            dist = Levenshtein.distance(ok, dk)
            if dist < best_dist:
                best_dist = dist
                best_match = dk
        
        if best_match and best_dist <= 3:
            mapped.append((ok, best_match))
            total_score += 1.0 - (best_dist / max(len(ok), len(best_match)))
        else:
            unmapped.append(ok)
    
    accuracy = total_score / len(orig_keys) if orig_keys else 0.0
    latency = (time.perf_counter() - start) * 1000
    
    return {
        "accuracy": accuracy,
        "latency_ms": latency,
        "mapped_fields": mapped,
        "unmapped_fields": unmapped,
        "batch_size": 1
    }

class LevenshteinReconciler:
    def reconcile(self, original: Dict, drifted: Dict) -> Dict:
        return _reconcile_single_pair((original, drifted))

    def reconcile_batch(self, pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        """Parallelise batch Levenshtein reconciliation across all available CPU cores."""
        num_workers = min(multiprocessing.cpu_count(), len(pairs))
        if num_workers <= 1:
            return [self.reconcile(orig, drift) for orig, drift in pairs]
        
        start = time.perf_counter()
        with multiprocessing.Pool(processes=num_workers) as pool:
            results = pool.map(_reconcile_single_pair, pairs)
            
        total_time = (time.perf_counter() - start) * 1000
        per_packet = total_time / len(pairs) if pairs else 0
        for r in results:
            r["latency_ms"] = per_packet
        return results
