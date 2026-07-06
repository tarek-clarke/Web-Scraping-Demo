import json
import time
import re
from typing import Dict, List, Tuple
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

class GemmaE4BReconciler:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4, llm_manager=None):
        self.batch_size = batch_size
        self.hardware_profile = hardware_profile
        self._llm = llm_manager
        self._own_manager = llm_manager is None

    def _get_manager(self):
        if self._llm is None:
            from ..inference.llm_manager import LLMManager
            import os as _os
            model_id = _os.environ.get("GEMMA_MODEL_ID", _os.environ.get("HF_MODEL_ID", "google/gemma-4-E4B-it"))
            device = "cuda" if self.hardware_profile in ("cuda", "rocm") else "mps" if self.hardware_profile == "silicon" else "cpu"
            self._llm = LLMManager(
                model_id=model_id,
                device=device,
                load_in_4bit=_os.environ.get("HF_LOAD_4BIT", "").lower() in ("1", "true", "yes"),
                load_in_8bit=_os.environ.get("HF_LOAD_8BIT", "").lower() in ("1", "true", "yes"),
            )
        return self._llm

    def _parse_json(self, text: str) -> Dict[str, str]:
        # Strip Gemma 4 reasoning tags
        text = re.sub(r'<\|think\|>.*?<\|/think\|>', '', text, flags=re.DOTALL)
        text = re.sub(r'```(?:json)?\s*', '', text)
        text = re.sub(r'```', '', text)
        # Try to find JSON object
        brace = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if brace:
            try:
                return json.loads(brace.group())
            except:
                pass
        return {}

    def _infer(self, original: Dict, drifted: Dict) -> Dict[str, str]:
        manager = self._get_manager()
        if not manager or not manager.is_loaded:
            return {}

        messages = [{
            "role": "user",
            "content": (
                f"Map original fields to drifted fields.\n"
                f"Original: {json.dumps(original)}\n"
                f"Drifted: {json.dumps(drifted)}\n"
                f"Output ONLY: {{\"original\": \"drifted\"}}"
            )
        }]
        response = manager.generate_response(messages, max_new_tokens=256, temperature=0.1, top_p=0.8)
        return self._parse_json(response)

    def reconcile_batch(self, pairs: List[Tuple[Dict, Dict]], progress_cb=None) -> List[Dict]:
        manager = self._get_manager()
        if not manager or not manager.is_loaded:
            return [{
                "accuracy": 0.0, "latency_ms": 0.0,
                "mapped_fields": [], "unmapped_fields": list(pairs[i][0].keys()),
                "batch_size": self.batch_size
            } for i in range(len(pairs))]

        start = time.perf_counter()
        results = []
        total = len(pairs)

        for i, (orig, drift) in enumerate(pairs):
            if progress_cb:
                progress_cb(i, total)

            parsed = self._infer(orig, drift)
            mapped = [(k, v) for k, v in parsed.items()]
            unmapped = [k for k in orig.keys() if k not in parsed]
            accuracy = len(mapped) / len(orig.keys()) if orig.keys() else 0.0
            results.append({
                "accuracy": accuracy,
                "latency_ms": 0.0,
                "mapped_fields": mapped,
                "unmapped_fields": unmapped,
                "batch_size": self.batch_size
            })

        total_time = (time.perf_counter() - start) * 1000
        per_packet = total_time / len(pairs) if pairs else 0
        for r in results:
            r["latency_ms"] = per_packet
        return results

    def reconcile(self, original: Dict, drifted: Dict) -> Dict:
        return self.reconcile_batch([(original, drifted)])[0]

    def __del__(self):
        if self._own_manager and self._llm:
            self._llm.unload()
