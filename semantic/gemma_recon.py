import time
from models.gemma_model import GemmaModel

class GemmaReconciler:
    def __init__(self, gemma_model: GemmaModel = None):
        self.gemma = gemma_model or GemmaModel()

    def reconcile(self, canonical_keys: list, query_key: str) -> dict:
        """
        Uses Gemma-4 to predict the matching canonical key.
        Confidence: Softmax/probability confidence score parsed from Gemma output.
        """
        start_time = time.perf_counter()
        
        result = self.gemma.predict_semantic_match(canonical_keys, query_key)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        
        # Ensure match is in the canonical_keys list (defense-in-depth)
        match_val = result.get("match", "unknown")
        confidence = float(result.get("confidence", 0.5))
        
        if match_val not in canonical_keys and canonical_keys:
            # Fallback to simple matching if Gemma hallucinates a key not in candidates
            match_val = canonical_keys[0]
            confidence = 0.1
            
        return {
            "match": match_val,
            "confidence": min(max(confidence, 0.0), 1.0),
            "latency_ms": elapsed_ms
        }
