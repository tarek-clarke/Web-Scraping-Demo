import re
import time
from typing import Dict, List, Tuple

class RegexReconciler:
    def __init__(self):
        self.patterns = {
            "temp": r"temp(erature)?",
            "speed": r"speed|velocity",
            "price": r"price|cost|value",
            "time": r"time(stamp)?|ts",
            "id": r"id|identifier"
        }

    def reconcile(self, original: Dict, drifted: Dict) -> Dict:
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
            matched = False
            for pattern_name, pattern in self.patterns.items():
                if re.search(pattern, ok, re.IGNORECASE):
                    for dk in drift_keys:
                        if re.search(pattern, dk, re.IGNORECASE):
                            mapped.append((ok, dk))
                            total_score += 1.0
                            matched = True
                            break
                if matched:
                    break
            
            if not matched:
                for dk in drift_keys:
                    if ok.lower() in dk.lower() or dk.lower() in ok.lower():
                        mapped.append((ok, dk))
                        total_score += 0.8
                        matched = True
                        break
            
            if not matched:
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

    def reconcile_batch(self, pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        start = time.perf_counter()
        results = [self.reconcile(orig, drift) for orig, drift in pairs]
        total_time = (time.perf_counter() - start) * 1000
        per_packet = total_time / len(pairs) if pairs else 0
        for r in results:
            r["latency_ms"] = per_packet
        return results
