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
        self._fallback_mode = False
        compatible, reason = self._check_transformers_compatibility(local_path)
        if not compatible:
            self.backend = "heuristic_fallback"
            self._fallback_mode = True
            self._load_error = reason
            print(f"[GemmaModel] Warning: local Gemma unavailable, using heuristic fallback ({reason}).")
            return

        try:
            super().__init__(local_path=local_path)
            self.backend = "local"
        except Exception as exc:
            # Keep the pipeline runnable even when the local Gemma checkpoint
            # cannot be loaded by the current transformers build.
            self.backend = "heuristic_fallback"
            self._fallback_mode = True
            self._load_error = str(exc)
            print(f"[GemmaModel] Warning: local Gemma unavailable, using heuristic fallback ({exc}).")

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
        if self._fallback_mode:
            return self._heuristic_query(prompt)
        return self.generate(prompt, max_new_tokens=max_tokens, temperature=temperature)

    def _heuristic_query(self, prompt: str) -> str:
        p = (prompt or "").lower()
        if "snake_case" in p:
            return "semantic_alias_field"
        if "paraphrase" in p:
            return "semantic paraphrase generated locally"
        return "semantic_fallback"

    def predict_semantic_match(self, canonical_keys: Sequence[str], query_key: str) -> dict:
        canonical_list = list(canonical_keys)
        if not canonical_list:
            return {"match": "unknown", "confidence": 0.0}

        if self._fallback_mode:
            query_norm = (query_key or "").strip().lower().replace("_", " ")
            best = canonical_list[0]
            best_score = -1
            for candidate in canonical_list:
                c_norm = str(candidate).strip().lower().replace("_", " ")
                token_overlap = len(set(query_norm.split()) & set(c_norm.split()))
                char_overlap = len(set(query_norm) & set(c_norm))
                score = token_overlap * 3 + char_overlap
                if score > best_score:
                    best = candidate
                    best_score = score
            confidence = 0.35 if best_score <= 0 else min(0.75, 0.35 + best_score * 0.03)
            return {"match": best, "confidence": confidence}

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
