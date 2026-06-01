"""Offline Gemma 4 E4B loader.

This module loads Gemma from a local Hugging Face cache or snapshot only.
No API endpoints or HTTP requests are used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, Dict, Sequence, Tuple

from models.gemma_local import GemmaLocal


class GemmaModel(GemmaLocal):
    """Backwards-compatible offline Gemma wrapper."""

    _instance_cache: ClassVar[Dict[Tuple[str], "GemmaModel"]] = {}

    def __new__(cls, local_path: str | Path | None = None):
        cache_key = (str(Path(local_path).expanduser().resolve()) if local_path else "__default__",)
        instance = cls._instance_cache.get(cache_key)
        if instance is None:
            instance = super().__new__(cls)
            cls._instance_cache[cache_key] = instance
            instance._initialized = False
        return instance

    def __init__(self, local_path: str | Path | None = None):
        if getattr(self, "_initialized", False):
            return

        super().__init__(local_path=local_path)
        self.backend = "local"
        self._initialized = True

    def query(self, prompt: str, temperature: float = 0.7, max_tokens: int = 256) -> str:
        return self.generate(prompt, max_new_tokens=max_tokens, temperature=temperature)

    def predict_semantic_match(self, canonical_keys: Sequence[str], query_key: str) -> dict:
        canonical_list = list(canonical_keys)
        if not canonical_list:
            return {"match": "unknown", "confidence": 0.0}

        prompt = (
            f"Given a list of canonical API schema fields: {canonical_list}\n"
            f"And a query key from a drifted/mutated schema: \"{query_key}\"\n\n"
            "Select the canonical field that is the best semantic match for this query key.\n"
            "Return your response strictly in the following JSON format:\n"
            '{"match": "canonical_field_name", "confidence": 0.0}'
        )

        raw_response = self.generate(prompt, max_new_tokens=128, temperature=0.0)
        
        # Strip conversational padding and markdown JSON wraps (like ```json ... ```)
        clean_response = raw_response.strip()
        if "```json" in clean_response:
            clean_response = clean_response.split("```json")[-1].split("```")[0].strip()
        elif "```" in clean_response:
            clean_response = clean_response.split("```")[-1].split("```")[0].strip()

        try:
            if "{" in clean_response and "}" in clean_response:
                clean_response = clean_response[clean_response.index("{") : clean_response.rindex("}") + 1]
            parsed = json.loads(clean_response)
        except Exception:
            parsed = {}

        match_value = parsed.get("match", canonical_list[0])
        if match_value not in canonical_list:
            match_value = canonical_list[0]

        confidence_value = parsed.get("confidence", 0.0)
        try:
            confidence_value = float(confidence_value)
        except Exception:
            confidence_value = 0.0

        return {"match": match_value, "confidence": max(0.0, min(confidence_value, 1.0))}


__all__ = ["GemmaModel"]
