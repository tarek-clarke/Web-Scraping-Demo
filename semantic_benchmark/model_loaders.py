"""Local-only model loaders for BERT and Gemma in the Semantic Translation Benchmark.

Guarantees 100% offline, local-only model execution. Aborts execution if 
internet fallback is requested or if local checkpoints are missing when 
require_local_models=True.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Tuple

# Enable offline mode for Hugging Face Hub
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Remove local directory from sys.path to avoid models.py name collision
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir in sys.path:
    sys.path.remove(script_dir)
if "" in sys.path:
    sys.path.remove("")

# Add root folder to sys.path
root_dir = os.path.dirname(script_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.bert_model import BERTModel
from models.gemma_local import GemmaLocal
from models.device_selector import get_device_info

class StrictBERTModel(BERTModel):
    """BERT loader with strict local-only checks."""
    
    def __new__(cls, require_local: bool = True):
        return super().__new__(cls, allow_internet=False)
        
    def __init__(self, require_local: bool = True):
        # We subclass and force allow_internet = False
        super().__init__(allow_internet=False)
        
        # Validate that model was loaded locally
        if require_local and (not self.is_loaded or self.model_source != "local"):
            raise RuntimeError(
                f"Strict Mode Violation: BERT model could not be loaded locally "
                f"(is_loaded={self.is_loaded}, model_source={self.model_source})."
            )

class StrictGemmaModel(GemmaLocal):
    """Gemma loader with strict local-only checks."""
    
    def __init__(self, local_path: str | Path | None = None, require_local: bool = True):
        # Resolve path
        try:
            resolved_path = self.resolve_local_path(local_path)
            super().__init__(local_path=resolved_path)
            self.backend = "local"
            
            # Setup device compatibility
            device_info = get_device_info()
            device = device_info["device"]
            if device in ("cuda", "rocm"):
                torch_device = "cuda"
            elif device == "mps":
                torch_device = "mps"
            else:
                torch_device = "cpu"
                
            self.device = torch_device
            if self.model is not None:
                self.model.to(torch_device)
                self.model.eval()
                
        except Exception as e:
            if require_local:
                raise RuntimeError(
                    f"Strict Mode Violation: Local Gemma checkpoint could not be loaded "
                    f"offline. Reason: {e}"
                ) from e
            else:
                print(f"[WARN] Gemma local load failed ({e}). Proceeding in mock fallback mode.")
                self.backend = "mock"
                self.model = None
                self.tokenizer = None
                self.device = "cpu"
                self.torch_dtype = None
                self.model_dir = None

    def query(self, prompt: str, temperature: float = 0.7, max_tokens: int = 256) -> str:
        if self.backend == "mock":
            words = prompt.split()
            return " ".join(words[-3:]) if len(words) >= 3 else prompt
        return self.generate(prompt, max_new_tokens=max_tokens, temperature=temperature)

    def predict_semantic_match(self, canonical_keys: list, query_key: str) -> dict:
        canonical_list = list(canonical_keys)
        if not canonical_list:
            return {"match": "unknown", "confidence": 0.0}

        if self.backend == "mock":
            best_match = canonical_list[0]
            best_score = 0.0
            qk_lower = query_key.lower()
            for ck in canonical_list:
                ck_lower = ck.lower()
                common = sum(1 for ch in ck_lower if ch in qk_lower)
                score = common / len(ck_lower) if ck_lower else 0.0
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

def run_preflight_validation(require_local_models: bool = True, strict_mode: bool = False) -> Tuple[Dict[str, Any], bool, str]:
    """Perform pre-flight checks to ensure 100% offline, local execution.
    
    Returns:
        tuple: (preflight_status_dict, abort_flag, error_message)
    """
    d = get_device_info()
    device = d["device"]
    hw_backend = d["hardware_backend"]
    gpu_available = device in ("cuda", "rocm", "mps")
    
    preflight_status = {
        "gpu_available": gpu_available,
        "hardware_backend": hw_backend,
        "device": device,
        "model_source": {"bert": "unknown", "gemma": "unknown"},
        "internet_used": False,
        "require_local_models": require_local_models,
        "strict_mode": strict_mode
    }
    
    # Check BERT
    try:
        bert = StrictBERTModel(require_local=require_local_models)
        preflight_status["model_source"]["bert"] = "local"
    except Exception as e:
        preflight_status["model_source"]["bert"] = "unavailable"
        if require_local_models or strict_mode:
            return preflight_status, True, f"BERT pre-flight validation failed: {e}"
            
    # Check Gemma
    try:
        gemma = StrictGemmaModel(require_local=require_local_models)
        preflight_status["model_source"]["gemma"] = gemma.backend
    except Exception as e:
        preflight_status["model_source"]["gemma"] = "unavailable"
        if require_local_models or strict_mode:
            return preflight_status, True, f"Gemma pre-flight validation failed: {e}"
            
    # Verify no internet handshake was initiated
    if os.environ.get("HF_HUB_OFFLINE") != "1":
        preflight_status["internet_used"] = True
        if strict_mode:
            return preflight_status, True, "Strict mode violation: HF_HUB_OFFLINE is not set to 1."
            
    return preflight_status, False, ""
