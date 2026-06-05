import json
import os
import time
import re
from typing import Dict, List, Tuple
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

class GemmaE4BReconciler:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4):
        model_dir = str(ROOT / "models" / "gemma-4-e4b-it")
        self.batch_size = batch_size
        self.model = None
        self.hardware_profile = hardware_profile
        self.model_path = None
        candidates = [
            os.path.join(model_dir, "gemma-4-E4B-it-Q4_K_M.gguf"),
            os.path.join(model_dir, "Q4_K_M.gguf"),
        ]
        for path in candidates:
            if os.path.exists(path):
                self.model_path = path
                break
        if self.model_path is None:
            self.model_path = candidates[0]
        self._load_model()

    def _load_model(self):
        try:
            if not os.path.exists(self.model_path):
                print(f"ERROR: Gemma E4B not found at {self.model_path}")
                return
            from llama_cpp import Llama
            n_gpu = -1 if self.hardware_profile in ["cuda", "rocm"] else 0
            self.model = Llama(model_path=self.model_path, n_ctx=2048, n_gpu_layers=n_gpu, verbose=False)
        except Exception as e:
            print(f"Gemma E4B not available: {e}")

    def _parse_json(self, text: str) -> Dict[str, str]:
        brace = re.search(r'\{.*\}', text, re.DOTALL)
        if brace:
            try:
                return json.loads(brace.group())
            except:
                pass
        return {}

    def reconcile_batch(self, pairs: List[Tuple[Dict, Dict]]) -> List[Dict]:
        if not self.model:
            return [{"accuracy": 0.0, "latency_ms": 0.0, "mapped_fields": [], "unmapped_fields": list(pairs[i][0].keys()), "batch_size": self.batch_size} for i in range(len(pairs))]

        start = time.perf_counter()
        results = []

        for orig, drift in pairs:
            messages = [{
                "role": "user",
                "content": f"Map fields from original JSON to drifted JSON.\nOriginal: {json.dumps(orig)}\nDrifted: {json.dumps(drift)}\nReturn JSON: {{\"original_field\": \"drifted_field\"}}"
            }]
            try:
                output = self.model.create_chat_completion(messages, max_tokens=256, temperature=0.1)
                text = output["choices"][0]["message"]["content"]
                parsed = self._parse_json(text)
            except:
                parsed = {}

            mapped = [(k, v) for k, v in parsed.items()]
            unmapped = [k for k in orig.keys() if k not in parsed]
            accuracy = len(mapped) / len(orig.keys()) if orig.keys() else 0.0
            results.append({"accuracy": accuracy, "latency_ms": 0.0, "mapped_fields": mapped, "unmapped_fields": unmapped, "batch_size": self.batch_size})

        total_time = (time.perf_counter() - start) * 1000
        per_packet = total_time / len(pairs) if pairs else 0
        for r in results:
            r["latency_ms"] = per_packet
        return results

    def reconcile(self, original: Dict, drifted: Dict) -> Dict:
        return self.reconcile_batch([(original, drifted)])[0]
