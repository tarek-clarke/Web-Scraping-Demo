import json
import os
import time
from typing import Dict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

class GemmaE4BReconciler:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4):
        self.model_path = str(ROOT / "models" / "gemma4-e4b-it.gguf")
        self.batch_size = batch_size
        self.model = None
        self._load_model(hardware_profile)

    def _load_model(self, hardware_profile: str):
        try:
            if not os.path.exists(self.model_path):
                print(f"Gemma E4B not found at {self.model_path}")
                print("Downloading from HuggingFace and saving locally...")
                try:
                    from huggingface_hub import hf_hub_download
                    os.makedirs(str(ROOT / "models"), exist_ok=True)
                    downloaded = hf_hub_download(
                        repo_id="google/gemma-4-e4b-it-GGUF",
                        filename="gemma-4-e4b-it-Q4_K_M.gguf",
                        local_dir=str(ROOT / "models"),
                        local_dir_use_symlinks=False
                    )
                    self.model_path = downloaded
                    print(f"Gemma E4B saved to {downloaded} (future runs will use local copy)")
                except Exception as hf_err:
                    print(f"HuggingFace download failed: {hf_err}")
                    print("Run: ./models/download_from_r2.sh")
                    return

            from llama_cpp import Llama
            n_gpu_layers = -1 if hardware_profile in ["cuda", "rocm"] else 0
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=2048,
                n_gpu_layers=n_gpu_layers,
                verbose=False
            )
        except Exception as e:
            print(f"Gemma E4B model not available: {e}")

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

        prompt = f"""Map drifted JSON fields to original fields.
Original: {json.dumps(original)}
Drifted: {json.dumps(drifted)}
Return JSON mapping: {{"original_field": "drifted_field"}}"""

        try:
            output = self.model(prompt, max_tokens=512, temperature=0.1)
            result_text = output["choices"][0]["text"].strip()
            mapping = json.loads(result_text)

            mapped = list(mapping.items())
            unmapped = [k for k in original.keys() if k not in mapping]
            accuracy = len(mapped) / len(original.keys()) if original.keys() else 0.0
        except:
            mapped = []
            unmapped = list(original.keys())
            accuracy = 0.0

        latency = (time.perf_counter() - start) * 1000

        return {
            "accuracy": accuracy,
            "latency_ms": latency,
            "mapped_fields": mapped,
            "unmapped_fields": unmapped,
            "batch_size": self.batch_size
        }
