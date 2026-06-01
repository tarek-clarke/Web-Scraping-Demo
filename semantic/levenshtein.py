import time

try:
    from cpp_accel import levenshtein_cpp
except ImportError:
    levenshtein_cpp = None

class LevenshteinReconciler:
    @staticmethod
    def distance(s1: str, s2: str) -> int:
        if levenshtein_cpp is not None:
            try:
                return levenshtein_cpp(s1, s2)
            except Exception:
                pass

        if len(s1) < len(s2):
            return LevenshteinReconciler.distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def reconcile(self, canonical_keys: list, query_key: str) -> dict:
        """
        Finds the closest matching canonical key using Levenshtein distance.
        """
        start_time = time.perf_counter()
        
        if not canonical_keys:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return {"match": "unknown", "confidence": 0.0, "latency_ms": elapsed}

        best_match = canonical_keys[0]
        min_dist = float("inf")
        
        for c_key in canonical_keys:
            dist = self.distance(c_key, query_key)
            if dist < min_dist:
                min_dist = dist
                best_match = c_key
                
        max_len = max(1, len(query_key), len(best_match))
        confidence = 1.0 - (min_dist / max_len)
        confidence = min(max(confidence, 0.0), 1.0)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        
        return {
            "match": best_match,
            "confidence": confidence,
            "latency_ms": elapsed_ms
        }
