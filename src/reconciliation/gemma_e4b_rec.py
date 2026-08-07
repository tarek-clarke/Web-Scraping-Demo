import json
import time
import re
from typing import Dict, List, Tuple
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

class GemmaE2BReconciler:
    def __init__(self, hardware_profile: str = "cpu", batch_size: int = 4, llm_manager=None,
                 model_env: str = "GEMMA_MODEL_ID", default_model_id: str = "google/gemma-4-E2B-it",
                 max_new_tokens: int = 64):
        self.batch_size = batch_size
        self.hardware_profile = hardware_profile
        self._llm = llm_manager
        self._own_manager = llm_manager is None
        self.model_env = model_env
        self.default_model_id = default_model_id
        self.max_new_tokens = max_new_tokens

    def _get_manager(self):
        if self._llm is None:
            from ..inference.llm_manager import LLMManager
            import os as _os
            model_id = _os.environ.get(self.model_env, _os.environ.get("HF_MODEL_ID", self.default_model_id))
            device = "cuda" if self.hardware_profile in ("cuda", "rocm") else "mps" if self.hardware_profile == "silicon" else "cpu"
            self._llm = LLMManager(
                model_id=model_id,
                device=device,
                load_in_4bit=_os.environ.get("HF_LOAD_4BIT", "").lower() in ("1", "true", "yes"),
                load_in_8bit=_os.environ.get("HF_LOAD_8BIT", "").lower() in ("1", "true", "yes"),
            )
        if not self._llm.is_loaded:
            # LLMManager instances are shared by model ID; oracle passes
            # deliberately unload them between methods to cap VRAM use.
            if not self._llm.load():
                raise RuntimeError(f"Failed to load local LLM: {self.default_model_id}")
        return self._llm

    def _parse_json(self, text: str) -> Dict[str, str]:
        # Strip Gemma 4 reasoning tags.
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
        response = manager.generate_response(messages, max_new_tokens=self.max_new_tokens, temperature=0.0, top_p=1.0)
        return self._parse_json(response)

    def reconcile_batch(self, pairs: List[Tuple[Dict, Dict]], progress_cb=None) -> List[Dict]:
        manager = self._get_manager()
        if not manager or not manager.is_loaded:
            raise RuntimeError(f"Local LLM is not loaded: {self.default_model_id}")

        start = time.perf_counter()
        results = []
        total = len(pairs)
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
        pairs = coerced_pairs
        
        # Sub-batching into self.batch_size chunks for GPU batch generation
        chunk_size = max(1, self.batch_size)
        for chunk_idx in range(0, total, chunk_size):
            chunk_pairs = pairs[chunk_idx:chunk_idx + chunk_size]
            batch_messages = []
            for orig, drift in chunk_pairs:
                batch_messages.append([{
                    "role": "user",
                    "content": (
                        f"Map original fields to drifted fields.\n"
                        f"Original: {json.dumps(orig)}\n"
                        f"Drifted: {json.dumps(drift)}\n"
                        f"Output ONLY: {{\"original\": \"drifted\"}}"
                    )
                }])

            responses = manager.generate_batch_responses(batch_messages, max_new_tokens=self.max_new_tokens, temperature=0.0, top_p=1.0)
            
            for offset, (orig, drift) in enumerate(chunk_pairs):
                idx = chunk_idx + offset
                if progress_cb:
                    progress_cb(idx, total)
                
                resp_text = responses[offset] if offset < len(responses) else ""
                parsed = self._parse_json(resp_text)
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


GemmaE4BReconciler = GemmaE2BReconciler
