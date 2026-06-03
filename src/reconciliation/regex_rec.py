import re
import time
from typing import Dict, List

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
