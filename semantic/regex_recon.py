import re
import time

class RegexReconciler:
    def __init__(self):
        # Predefined regex patterns for common canonical fields
        self.patterns = {
            "temperature": [r"temp", r"therm", r"deg", r"heat", r"cel"],
            "price": [r"price", r"cost", r"amount", r"monetary", r"usd", r"val"],
            "wind_speed": [r"wind", r"velocity", r"speed", r"breeze", r"kph", r"mph"],
            "capsule_serial": [r"capsule", r"serial", r"id", r"tag"],
            "driver_name": [r"driver", r"pilot", r"name", r"code", r"number"]
        }

    def reconcile(self, canonical_keys: list, query_key: str) -> dict:
        """
        Finds a match using regular expressions.
        Confidence: 1.0 if pattern matches, 0.0 if not.
        """
        start_time = time.perf_counter()
        
        q_lower = query_key.lower()
        match_key = None
        
        # 1. First try exact regex search on the canonical list
        for c_key in canonical_keys:
            # Check if query matches the canonical key directly or via simple word boundaries
            pattern = re.compile(rf".*{re.escape(c_key)}.*|.*{re.escape(query_key)}.*", re.IGNORECASE)
            if pattern.match(c_key) or pattern.match(query_key):
                match_key = c_key
                break
                
        # 2. Try rule-based regex patterns
        if not match_key:
            for c_key in canonical_keys:
                patterns_to_check = self.patterns.get(c_key, [c_key])
                for p in patterns_to_check:
                    if re.search(p, q_lower):
                        match_key = c_key
                        break
                if match_key:
                    break

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        
        if match_key:
            return {
                "match": match_key,
                "confidence": 1.0,
                "latency_ms": elapsed_ms
            }
        else:
            # Miss: Return first candidate as fallback but with 0.0 confidence
            fallback = canonical_keys[0] if canonical_keys else "unknown"
            return {
                "match": fallback,
                "confidence": 0.0,
                "latency_ms": elapsed_ms
            }
ZO = RegexReconciler()
