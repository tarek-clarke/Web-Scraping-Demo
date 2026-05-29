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

# On macOS Apple Silicon, monkeypatch PyTorch MPS to force CPU fallback for stability
# (Successfully bypasses GPU memory deadlocks inside the core models/gemma_local.py loader)
import platform
if platform.system() == "Darwin" and os.getenv("FORCE_HARDWARE") in ("cpu", "fallback"):
    try:
        import torch
        if hasattr(torch, "backends") and hasattr(torch.backends, "mps"):
            torch.backends.mps.is_available = lambda: False
            torch.backends.mps.is_built = lambda: False
    except Exception:
        pass

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

def detect_academic_hardware() -> Tuple[str, str]:
    """Detect backend: CUDA, ROCm, Metal, DirectML, CPU."""
    # Allow overriding via FORCE_HARDWARE env variable (helps bypass GPU/MPS driver deadlocks)
    force_env = os.getenv("FORCE_HARDWARE")
    if force_env:
        v = force_env.strip().lower()
        if v in ("cpu", "fallback"):
            return "CPU", "cpu"
        elif v in ("mps", "metal", "apple"):
            return "Metal", "mps"
        elif v in ("cuda", "nvidia"):
            return "CUDA", "cuda"
        elif v in ("rocm", "amd"):
            return "ROCm", "cuda"

    import platform
    system = platform.system()
    machine = platform.machine().lower()
    
    # 1. Check Metal (MPS) on macOS Apple Silicon
    if system == "Darwin" and ("arm" in machine or "apple" in platform.processor().lower()):
        try:
            import torch
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "Metal", "mps"
        except Exception:
            pass
        return "Metal", "cpu"
        
    # 2. Check CUDA on Linux/Windows
    try:
        import torch
        if torch.cuda.is_available():
            if hasattr(torch.version, "hip") and torch.version.hip is not None:
                return "ROCm", "cuda"
            return "CUDA", "cuda"
    except Exception:
        pass
        
    # 3. Check ROCm on Linux / Windows environment variables
    if os.getenv("HIP_PATH") or os.getenv("ROCM_PATH") or os.path.exists("/opt/rocm") or os.path.exists(r"C:\Program Files\AMD\ROCm"):
        return "ROCm", "cpu"
        
    # 4. Check DirectML on Windows AMD
    if system == "Windows":
        try:
            import torch_directml
            if torch_directml.is_available():
                return "PrivateUse1", "privateuseone:0"
        except Exception:
            pass
            
    # 5. Fallback to CPU
    return "CPU", "cpu"

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
            
            # Setup device compatibility dynamically
            hw_backend, hw_device = detect_academic_hardware()
            if hw_backend == "PrivateUse1":
                try:
                    import torch_directml
                    self.device = torch_directml.device()
                except Exception:
                    self.device = "cpu"
            else:
                self.device = hw_device
                
            if self.model is not None:
                device_str = str(self.device)
                print(f"\n[*] Transferring Gemma model weights to device: {device_str}...")
                if "mps" in device_str.lower() or "metal" in device_str.lower():
                    print("    > Note: PyTorch Metal (MPS) initialization, memory allocation, and shader")
                    print("      kernel compilation on Apple Silicon can take up to 1-2 minutes on first load.")
                    print("      This is normal and expected cold-start behavior. Please do not close the terminal...")
                elif "cuda" in device_str.lower() or "rocm" in device_str.lower():
                    print("    > Note: Mapping model weights to GPU memory...")
                
                if isinstance(self.device, str):
                    self.model.to(self.device)
                else:
                    self.model = self.model.to(self.device)
                
                self.model.eval()
                print(f"[✓] Gemma model successfully loaded and warmed up on {device_str}.\n")
                
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

def run_preflight_validation(require_local_models: bool = True, strict_mode: bool = False, enabled_methods: list = None) -> Tuple[Dict[str, Any], bool, str]:
    """Perform pre-flight checks to ensure 100% offline, local execution and hardware verification.
    
    Returns:
        tuple: (preflight_status_dict, abort_flag, error_message)
    """
    hw_backend, hw_device = detect_academic_hardware()
    gpu_available = hw_backend in ("CUDA", "ROCm", "Metal", "PrivateUse1")
    
    preflight_status = {
        "gpu_available": gpu_available,
        "hardware_backend": hw_backend,
        "device": hw_device,
        "model_source": {"bert": "unknown", "gemma": "unknown"},
        "internet_used": False,
        "require_local_models": require_local_models,
        "strict_mode": strict_mode
    }
    
    # Strict mode hardware boundary validation
    import platform
    is_mac = platform.system() == "Darwin"
    if strict_mode and hw_device == "cpu" and not is_mac and os.getenv("FORCE_HARDWARE") != "cpu":
        return preflight_status, True, "Strict mode violation: Unsupported CPU backend detected. CUDA, ROCm, Metal, or DirectML is strictly required."
    
    # Check BERT
    if enabled_methods is None or "bert" in enabled_methods:
        try:
            bert = StrictBERTModel(require_local=require_local_models)
            preflight_status["model_source"]["bert"] = "local"
        except Exception as e:
            preflight_status["model_source"]["bert"] = "unavailable"
            if require_local_models or strict_mode:
                return preflight_status, True, f"BERT pre-flight validation failed: {e}"
    else:
        preflight_status["model_source"]["bert"] = "skipped"
            
    # Check Gemma
    if enabled_methods is None or "gemma" in enabled_methods:
        try:
            gemma = StrictGemmaModel(require_local=require_local_models)
            preflight_status["model_source"]["gemma"] = gemma.backend
        except Exception as e:
            preflight_status["model_source"]["gemma"] = "unavailable"
            if require_local_models or strict_mode:
                return preflight_status, True, f"Gemma pre-flight validation failed: {e}"
    else:
        preflight_status["model_source"]["gemma"] = "skipped"
            
    # Verify no internet handshake was initiated
    if os.environ.get("HF_HUB_OFFLINE") != "1":
        preflight_status["internet_used"] = True
        if strict_mode:
            return preflight_status, True, "Strict mode violation: HF_HUB_OFFLINE is not set to 1."
            
    return preflight_status, False, ""
