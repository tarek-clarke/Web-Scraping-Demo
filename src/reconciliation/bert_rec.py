import os
import time
from typing import Dict, List

class BERTReconciler:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4):
        self.device = "cuda" if hardware_profile in ["cuda", "rocm"] else "cpu"
        self.batch_size = batch_size
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            
            model_path = os.path.join(os.path.dirname(__file__), '../../models/all-MiniLM-L6-v2')
            
            if not os.path.exists(model_path):
                print(f"ERROR: BERT model not found at {model_path}")
                print("Run: ./models/download_from_r2.sh")
                return
            
            self.model = SentenceTransformer(model_path, device=self.device)
            print(f"BERT model loaded from local path: {model_path}")
        except Exception as e:
            print(f"BERT model not available: {e}")

    def reconcile(self, original: Dict, drifted: Dict) -> Dict:
        if not self.model:
            return {
                "accuracy": 0.0,
                "latency_ms": 0.0,
                "mapped_fields": [],
                "unmapped_fields": list(original.keys()),
                "batch_size": self.batch_size
            }
        
        start = time.perf_counter()
        
        orig_keys = list(original.keys())
        drift_keys = list(drifted.keys())
        
        orig_embeddings = self.model.encode(orig_keys, batch_size=self.batch_size)
        drift_embeddings = self.model.encode(drift_keys, batch_size=self.batch_size)
        
        mapped = []
        unmapped = []
        total_score = 0.0
        
        for i, ok in enumerate(orig_keys):
            best_match = None
            best_sim = 0.0
            
            for j, dk in enumerate(drift_keys):
                sim = self._cosine_similarity(orig_embeddings[i], drift_embeddings[j])
                if sim > best_sim:
                    best_sim = sim
                    best_match = dk
            
            if best_sim > 0.7:
                mapped.append((ok, best_match))
                total_score += best_sim
            else:
                unmapped.append(ok)
        
        accuracy = total_score / len(orig_keys) if orig_keys else 0.0
        latency = (time.perf_counter() - start) * 1000
        
        return {
            "accuracy": accuracy,
            "latency_ms": latency,
            "mapped_fields": mapped,
            "unmapped_fields": unmapped,
            "batch_size": self.batch_size
        }

    def _cosine_similarity(self, a, b):
        import numpy as np
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
