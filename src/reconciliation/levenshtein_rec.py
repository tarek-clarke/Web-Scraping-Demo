import time
from typing import Dict, List
import Levenshtein

class LevenshteinReconciler:
    def reconcile(self, original: Dict, drifted: Dict) -> Dict:
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
