import os
import time
from typing import Dict, List
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent

class BERTReconciler:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4):
        self.device = "cuda" if hardware_profile in ["cuda", "rocm"] else "cpu"
        self.batch_size = batch_size
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer

            model_path = str(ROOT / "models" / "all-MiniLM-L6-v2")

            if os.path.exists(model_path):
                self.model = SentenceTransformer(model_path, device=self.device)
                print(f"BERT loaded from local: {model_path}")
            else:
                print(f"BERT not found locally, downloading from HuggingFace to {model_path}...")
                self.model = SentenceTransformer('all-MiniLM-L6-v2', device=self.device)
                self.model.save(model_path)
                print(f"BERT saved to {model_path} (future runs will use local copy)")
        except Exception as e:
            print(f"BERT model not available: {e}")

    def reconcile(self, original: Dict, drifted: Dict) -> Dict:
        if not self.model:
            return {
                "accuracy": 0.0, "latency_ms": 0.0,
                "mapped_fields": [], "unmapped_fields": list(original.keys()),
                "batch_size": self.batch_size
            }

        start = time.perf_counter()

        orig_keys = list(original.keys())
        drift_keys = list(drifted.keys())

        if not orig_keys or not drift_keys:
            return {
                "accuracy": 0.0, "latency_ms": (time.perf_counter() - start) * 1000,
                "mapped_fields": [], "unmapped_fields": orig_keys,
                "batch_size": self.batch_size
            }

        orig_emb = self.model.encode(orig_keys, batch_size=self.batch_size)
        drift_emb = self.model.encode(drift_keys, batch_size=self.batch_size)

        # Vectorized cosine similarity: (N x D) @ (D x M) = N x M
        orig_norm = orig_emb / np.linalg.norm(orig_emb, axis=1, keepdims=True)
        drift_norm = drift_emb / np.linalg.norm(drift_emb, axis=1, keepdims=True)
        sim_matrix = np.dot(orig_norm, drift_norm.T)  # (n_orig x n_drift)

        mapped = []
        unmapped = []
        total_score = 0.0

        for i, ok in enumerate(orig_keys):
            best_idx = np.argmax(sim_matrix[i])
            best_sim = sim_matrix[i, best_idx]

            if best_sim > 0.7:
                mapped.append((ok, drift_keys[best_idx]))
                total_score += best_sim
            else:
                unmapped.append(ok)

        accuracy = total_score / len(orig_keys) if orig_keys else 0.0
        latency = (time.perf_counter() - start) * 1000

        return {
            "accuracy": accuracy, "latency_ms": latency,
            "mapped_fields": mapped, "unmapped_fields": unmapped,
            "batch_size": self.batch_size
        }
