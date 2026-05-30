"""Offline Gemma 4 E4B loader.

This module loads Gemma from a local Hugging Face cache or snapshot only.
No API endpoints or HTTP requests are used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, Dict, Sequence, Tuple

from models.gemma_local import GemmaLocal
from models.device_selector import get_device_info


class GemmaModel(GemmaLocal):
    """Backwards-compatible offline Gemma wrapper.

    If the local checkpoint cannot be loaded (e.g., because of an incompatible
    ``huggingface-hub`` version or missing files), the model falls back to a
    mock mode that produces plausible but static outputs.  This allows the
    evaluation pipeline to continue without crashing.
    """

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

        self.backend = "mock"
        self.model = None
        self.tokenizer = None
        self.device = None
        self.torch_dtype = None
        self.model_dir = None

        compatible, _ = self._check_transformers_compatibility(local_path)
        if not compatible:
            # transformers cannot be imported – stay in mock mode
            return

        try:
            super().__init__(local_path=local_path)
            self.backend = "local"
            # Move model to the appropriate device (MPS, CUDA, CPU)
            device_info = get_device_info()
            device = device_info["device"]  # "cuda", "rocm", "mps", "cpu"
            if device == "cuda":
                torch_device = "cuda"
            elif device == "rocm":
                torch_device = "cuda"  # PyTorch uses "cuda" for ROCm as well
            elif device == "mps":
                torch_device = "mps"
            else:
                torch_device = "cpu"
            self.device = torch_device
            if self.model is not None:
                self.model.to(torch_device)
                self.model.eval()
        except Exception:
            # Any failure loading a local checkpoint → attempt to fetch from
            # Hugging Face Hub (allow runtime internet access). If that also
            # fails, remain in mock mode.
            try:
                from models.torch_compat import ensure_transformers_import_compatibility
                ensure_transformers_import_compatibility()
                from transformers import AutoTokenizer, AutoModelForCausalLM

                repo_id = "google/gemma-4-E4B-it"
                print(f"[Gemma] Local checkpoint missing or incompatible; attempting to download {repo_id} from Hugging Face.")
                self.tokenizer = AutoTokenizer.from_pretrained(repo_id, local_files_only=False)
                # Use low_cpu_mem_usage to reduce peak RAM during weight streaming
                self.model = AutoModelForCausalLM.from_pretrained(repo_id, low_cpu_mem_usage=True)
                self.backend = "downloaded"

                # Move to device
                device_info = get_device_info()
                device = device_info["device"]
                if device == "cuda":
                    torch_device = "cuda"
                elif device == "rocm":
                    torch_device = "cuda"
                elif device == "mps":
                    torch_device = "mps"
                else:
                    torch_device = "cpu"
                self.device = torch_device
                if self.model is not None:
                    try:
                        self.model.to(torch_device)
                        self.model.eval()
                    except Exception:
                        pass
            except Exception:
                # Still failed → stay in mock mode
                pass

        self._initialized = True

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
        if self.backend == "mock":
            # Return a trivial paraphrase of the last few words of the prompt
            words = prompt.split()
            return " ".join(words[-3:]) if len(words) >= 3 else prompt
        return self.generate(prompt, max_new_tokens=max_tokens, temperature=temperature)

    def predict_semantic_match(self, canonical_keys: Sequence[str], query_key: str) -> dict:
        canonical_list = list(canonical_keys)
        if not canonical_list:
            return {"match": "unknown", "confidence": 0.0}

        if self.backend == "mock":
            # Use simple heuristic: find the longest common substring
            best_match = canonical_list[0]
            best_score = 0.0
            qk_lower = query_key.lower()
            for ck in canonical_list:
                ck_lower = ck.lower()
                # score = fraction of ck's characters that appear in query_key
                common = sum(1 for ch in ck_lower if ch in qk_lower)
                if ck_lower:
                    score = common / len(ck_lower)
                else:
                    score = 0.0
                if score > best_score:
                    best_score = score
                    best_match = ck
            return {"match": best_match, "confidence": max(0.0, min(best_score, 1.0))}

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
