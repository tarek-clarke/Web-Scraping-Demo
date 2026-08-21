# --- Mock amdsmi to work around PyTorch/ROCm packaging bug ---
import sys
from types import ModuleType
if 'amdsmi' not in sys.modules:
    dummy = ModuleType('amdsmi')
    dummy.AmdSmiException = Exception
    dummy.amdsmi_init = lambda: None
    sys.modules['amdsmi'] = dummy

import os
import time
import threading
from typing import Dict, List, Tuple
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent

class BERTReconciler:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4):
        self.hardware_profile = hardware_profile
        self.device = "cuda" if hardware_profile in ["cuda", "rocm"] else "cpu"
        self.batch_size = batch_size
        self.model = None
        self._lock = threading.Lock()
        self._load_model()

    def _load_model(self):
        try:
            from ..inference.huggingface_compat import install_hub_compat
            install_hub_compat()
            from sentence_transformers import SentenceTransformer
            model_path = str(ROOT / "models" / "bert-minilm-v2")
            if os.path.exists(model_path):
                self.model = SentenceTransformer(model_path, device=self.device)
                print(f"BERT loaded from: {model_path}")
                return

            print("BERT model not found locally; downloading from HuggingFace...")
            import multiprocessing
            result_queue = multiprocessing.Queue()
            p = multiprocessing.Process(
                target=self._download_bert,
                args=(result_queue,)
            )
            p.start()
            download_timeout = int(os.environ.get("RAP_BERT_DOWNLOAD_TIMEOUT_SECONDS", "600"))
            print(
                f"Waiting up to {download_timeout}s for the scratch-cached MiniLM download...",
                flush=True,
            )
            p.join(timeout=download_timeout)
            if p.is_alive():
                p.terminate()
                p.join()
                raise TimeoutError(
                    f"BERT download timed out after {download_timeout}s"
                )
            if os.path.exists(model_path) and os.listdir(model_path):
                self.model = SentenceTransformer(model_path, device=self.device)
                print(f"BERT loaded from: {model_path}")
            else:
                raise RuntimeError("Download failed")
        except Exception as e:
            raise RuntimeError(
                "MiniLM could not load; benchmark mock embeddings and silent CPU "
                f"fallback are disabled: {e}"
            ) from e

    def _download_bert(self, result_queue):
        try:
            from sentence_transformers import SentenceTransformer
            m = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device=self.device)
            os.makedirs(str(ROOT / "models" / "bert-minilm-v2"), exist_ok=True)
            m.save(str(ROOT / "models" / "bert-minilm-v2"))
        except Exception as e:
            pass

    def _init_mock_embedder(self):
        import hashlib, math
        self._mock = True

    def reconcile_batch(self, pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        if not self.model:
            return [{
                "accuracy": 0.0, "latency_ms": 0.0,
                "mapped_fields": [], "unmapped_fields": list(pairs[i][0].keys()),
                "batch_size": self.batch_size
            } for i in range(len(pairs))]

        start = time.perf_counter()

        all_keys = set()
        coerced_pairs = []
        for orig, drift in pairs:
            if isinstance(orig, list):
                orig = {str(i): v for i, v in enumerate(orig)}
            elif not isinstance(orig, dict):
                orig = {}
            if isinstance(drift, list):
                drift = {str(i): v for i, v in enumerate(drift)}
            elif not isinstance(drift, dict):
                drift = {}
            coerced_pairs.append((orig, drift))
            all_keys.update(str(k) for k in orig.keys())
            all_keys.update(str(k) for k in drift.keys())
        pairs = coerced_pairs
        unique_keys = list(all_keys)
        
        if not unique_keys:
            elapsed = (time.perf_counter() - start) * 1000 / len(pairs) if pairs else 0
            return [{
                "accuracy": 0.0, "latency_ms": elapsed,
                "mapped_fields": [], "unmapped_fields": list(pairs[i][0].keys()),
                "batch_size": self.batch_size
            } for i in range(len(pairs))]
        
        with self._lock:
            all_emb = self.model.encode(unique_keys, batch_size=max(self.batch_size, len(unique_keys)))
        key_to_emb = {k: all_emb[i] for i, k in enumerate(unique_keys)}
        
        total_time = (time.perf_counter() - start) * 1000
        per_packet_latency = total_time / len(pairs) if pairs else 0
        
        results = []
        for orig, drift in pairs:
            orig_keys = [str(k) for k in orig.keys()]
            drift_keys = [str(k) for k in drift.keys()]

            if not orig_keys or not drift_keys:
                results.append({
                    "accuracy": 0.0, "latency_ms": per_packet_latency,
                    "mapped_fields": [], "unmapped_fields": orig_keys,
                    "batch_size": self.batch_size
                })
                continue

            orig_emb = np.array([key_to_emb[k] for k in orig_keys])
            drift_emb = np.array([key_to_emb[k] for k in drift_keys])

            orig_norm = orig_emb / np.linalg.norm(orig_emb, axis=1, keepdims=True)
            drift_norm = drift_emb / np.linalg.norm(drift_emb, axis=1, keepdims=True)
            sim_matrix = np.dot(orig_norm, drift_norm.T)

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
            results.append({
                "accuracy": accuracy, "latency_ms": per_packet_latency,
                "mapped_fields": mapped, "unmapped_fields": unmapped,
                "batch_size": self.batch_size
            })

        return results

    def reconcile(self, original: Dict, drifted: Dict) -> Dict:
        return self.reconcile_batch([(original, drifted)])[0]
