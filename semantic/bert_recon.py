from __future__ import annotations

import time
from models.model_registry import get_shared_bert_model

class BERTReconciler:
    def __init__(self, bert_model: BERTModel = None):
        self.bert = bert_model or get_shared_bert_model()
        self._canonical_embedding_cache = {}

    @staticmethod
    def _dot_product(vec1, vec2) -> float:
        return sum(a * b for a, b in zip(vec1, vec2))

    def clear_caches(self) -> None:
        self._canonical_embedding_cache.clear()
        if hasattr(self.bert, "clear_caches"):
            self.bert.clear_caches()

    def reconcile(self, canonical_keys: list, query_key: str) -> dict:
        """
        Uses BERT to find the best semantic canonical match.
        Confidence: Cosine similarity normalized to [0, 1].
        """
        start_time = time.perf_counter()
        
        if not canonical_keys:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return {"match": "unknown", "confidence": 0.0, "latency_ms": elapsed}

        canonical_key_tuple = tuple(canonical_keys)
        canonical_embeddings = self._canonical_embedding_cache.get(canonical_key_tuple)
        if canonical_embeddings is None:
            canonical_embeddings = self.bert.get_embeddings_batch(canonical_keys)
            self._canonical_embedding_cache[canonical_key_tuple] = canonical_embeddings

        query_embedding = self.bert.get_embedding(query_key)

        best_match = canonical_keys[0]
        max_similarity = -1.0

        for c_key, c_emb in zip(canonical_keys, canonical_embeddings):
            sim = self._dot_product(c_emb, query_embedding)
            if sim > max_similarity:
                max_similarity = sim
                best_match = c_key
                
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        
        return {
            "match": best_match,
            "confidence": float(max_similarity),
            "latency_ms": elapsed_ms
        }
