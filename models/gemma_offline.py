"""Offline Gemma 4 E4B loader.

This module loads Gemma from a local Hugging Face cache or snapshot only.
No API endpoints or HTTP requests are used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from models.gemma_local import GemmaLocal


class GemmaModel(GemmaLocal):
    """Backwards-compatible offline Gemma wrapper."""

    def __init__(self, local_path: str | Path | None = None):
        compatible, reason = self._check_transformers_compatibility(local_path)
        if not compatible:
            raise RuntimeError(f"Local Gemma checkpoint is unavailable: {reason}")

        try:
            super().__init__(local_path=local_path)
            self.backend = "local"
        except Exception as exc:
            raise RuntimeError(f"Failed to load local Gemma checkpoint: {exc}") from exc

    @staticmethod
    def _check_transformers_compatibility(local_path: str | Path | None):
        """Return (is_compatible, reason)."""
        try:
            from transformers.models.auto.configuration_auto import CONFIG_MAPPING
        except Exception as exc:
            return False, f"transformers unavailable ({exc})"

        try:
            resolved = GemmaLocal.resolve_local_path(local_path)
        except Exception as exc:
            return False, f"checkpoint discovery failed ({exc})"

        config_path = Path(resolved) / "config.json"
        if not config_path.is_file():
            snapshots = Path(resolved) / "snapshots"
            if snapshots.is_dir():
                for snap in sorted(snapshots.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                    candidate = snap / "config.json"
                    if candidate.is_file():
                        config_path = candidate
                        break

        if not config_path.is_file():
            return False, "missing config.json"

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                model_type = json.load(f).get("model_type")
        except Exception as exc:
            return False, f"invalid config.json ({exc})"

        if not model_type:
            return False, "config.json has no model_type"

        if model_type not in CONFIG_MAPPING:
            return False, f"transformers does not support model_type '{model_type}'"

        return True, "ok"

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
        try:
            if "{" in raw_response and "}" in raw_response:
                raw_response = raw_response[raw_response.index("{") : raw_response.rindex("}") + 1]
            parsed = json.loads(raw_response)
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
