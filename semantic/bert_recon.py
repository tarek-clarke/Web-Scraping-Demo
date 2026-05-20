import time
from models.bert_model import BERTModel

class BERTReconciler:
    def __init__(self, bert_model: BERTModel = None):
        self.bert = bert_model or BERTModel()

    def reconcile(self, canonical_keys: list, query_key: str) -> dict:
        """
        Uses BERT to find the best semantic canonical match.
        Confidence: Cosine similarity normalized to [0, 1].
        """
        start_time = time.perf_counter()
        
        if not canonical_keys:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return {"match": "unknown", "confidence": 0.0, "latency_ms": elapsed}

        best_match = canonical_keys[0]
        max_similarity = -1.0
        
        for c_key in canonical_keys:
            # We already normalize the similarity in bert_model to [0, 1]
            sim = self.bert.cosine_similarity(c_key, query_key)
            if sim > max_similarity:
                max_similarity = sim
                best_match = c_key
                
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        
        return {
            "match": best_match,
            "confidence": float(max_similarity),
            "latency_ms": elapsed_ms
        }
