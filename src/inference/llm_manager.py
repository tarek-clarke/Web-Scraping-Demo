import os
import sys
import platform
import threading
from typing import Any, Dict, List, Optional, Iterator, Union
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def _detect_device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _resolve_dtype(requested: str, device: str):
    import torch
    if requested == "auto":
        if device == "cuda":
            return torch.bfloat16
        elif device == "mps":
            return torch.float16
        else:
            return torch.float32
    mapping = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    return mapping.get(requested, torch.bfloat16 if device == "cuda" else torch.float32)


def _resolve_attn(requested: str, model_id: str, device: str) -> Optional[str]:
    if requested == "auto":
        if device == "cuda":
            return "flash_attention_2"
        return "sdpa" if device == "mps" else None
    if requested.lower() == "none":
        return None
    return requested


class LLMManager:
    _instances: Dict[str, "LLMManager"] = {}
    _lock = threading.Lock()

    def __new__(cls, model_id: Optional[str] = None, **kwargs):
        key = model_id or os.environ.get("HF_MODEL_ID", "google/gemma-4-E4B-it")
        with cls._lock:
            if key not in cls._instances:
                instance = super().__new__(cls)
                instance._key = key
                instance._initialized = False
                cls._instances[key] = instance
        return cls._instances[key]

    def __init__(self, model_id: Optional[str] = None, **kwargs):
        if getattr(self, "_initialized", False):
            return

        self.model_id = model_id or os.environ.get("HF_MODEL_ID", "google/gemma-4-E4B-it")
        self.hf_token = kwargs.get("hf_token") or os.environ.get("HF_TOKEN", None)
        self.max_tokens = int(kwargs.get("max_reasoning_tokens") or os.environ.get("LLM_MAX_REASONING_TOKENS", "2048"))
        self.local_path = kwargs.get("local_model_path") or os.environ.get("HF_LOCAL_MODEL_PATH", None)
        self.load_in_4bit = kwargs.get("load_in_4bit") or os.environ.get("HF_LOAD_4BIT", "").lower() in ("1", "true", "yes")
        self.load_in_8bit = kwargs.get("load_in_8bit") or os.environ.get("HF_LOAD_8BIT", "").lower() in ("1", "true", "yes")

        self.device = kwargs.get("device") or _detect_device()
        self.torch_dtype = _resolve_dtype(
            kwargs.get("torch_dtype") or os.environ.get("HF_TORCH_DTYPE", "auto"),
            self.device
        )
        self.attn_impl = _resolve_attn(
            kwargs.get("attn_implementation") or os.environ.get("HF_ATTN_IMPL", "auto"),
            self.model_id, self.device
        )

        self.model = None
        self.tokenizer = None
        self.is_loaded = False
        self._initialized = True

        if not kwargs.get("lazy", False):
            self.load()

    def load(self) -> bool:
        if self.is_loaded:
            return True
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

            model_path = self.local_path or self.model_id

            load_kwargs: Dict[str, Any] = {
                "dtype": self.torch_dtype,
                "trust_remote_code": True,
            }

            if self.attn_impl:
                load_kwargs["attn_implementation"] = self.attn_impl

            if self.load_in_4bit:
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                )
                load_kwargs["device_map"] = "auto"
            elif self.load_in_8bit:
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_8bit=True,
                )
                load_kwargs["device_map"] = "auto"
            else:
                load_kwargs["device_map"] = self.device if self.device != "mps" else "mps"

            if self.hf_token:
                load_kwargs["token"] = self.hf_token

            print(f"[LLM] Loading {model_path} on {self.device} (dtype={self.torch_dtype}, attn={self.attn_impl})")
            self.model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)

            tok_kwargs = {"trust_remote_code": True}
            if self.hf_token:
                tok_kwargs["token"] = self.hf_token
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, **tok_kwargs)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            self.model.eval()
            self.is_loaded = True
            print(f"[LLM] Model loaded: {self.model_id} (device={self.model.device})")
            return True
        except Exception as e:
            print(f"[LLM] Failed to load model: {e}")
            self.is_loaded = False
            return False

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: Optional[int] = None,
        temperature: float = 0.1,
        top_p: float = 0.8,
        do_sample: bool = False,
    ) -> str:
        if not self.is_loaded:
            if not self.load():
                return ""

        try:
            import torch

            prompt = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self.tokenizer(prompt, return_tensors="pt")
            if self.device in ("cuda", "mps"):
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

            gen_kwargs: Dict[str, Any] = {
                "max_new_tokens": max_new_tokens or 256,
                "temperature": temperature,
                "top_p": top_p,
                "do_sample": do_sample,
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
            }

            with torch.no_grad():
                outputs = self.model.generate(**inputs, **gen_kwargs)

            response = self.tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True
            )
            return response.strip()
        except Exception as e:
            print(f"[LLM] Generation error: {e}")
            return ""

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: Optional[int] = None,
        temperature: float = 0.1,
        top_p: float = 0.8,
    ) -> Iterator[str]:
        if not self.is_loaded:
            if not self.load():
                yield ""
                return

        try:
            import torch
            from transformers import TextStreamer

            prompt = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self.tokenizer(prompt, return_tensors="pt")
            if self.device in ("cuda", "mps"):
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

            streamer = TextStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)

            gen_kwargs: Dict[str, Any] = {
                "max_new_tokens": max_new_tokens or 256,
                "temperature": temperature,
                "top_p": top_p,
                "do_sample": True,
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "streamer": streamer,
            }

            import threading as _thr
            result = {"done": False}

            def _run():
                with torch.no_grad():
                    self.model.generate(**inputs, **gen_kwargs)
                result["done"] = True

            _thr.Thread(target=_run, daemon=True).start()
            while not result["done"]:
                yield ""
        except Exception as e:
            print(f"[LLM] Stream error: {e}")
            yield ""

    def reset_kv_cache(self) -> None:
        if self.is_loaded and hasattr(self.model, "reset"):
            self.model.reset()

    def unload(self) -> None:
        if self.is_loaded:
            self.reset_kv_cache()
            import torch
            if hasattr(self.model, "cpu"):
                self.model.cpu()
            self.model = None
            self.tokenizer = None
            self.is_loaded = False
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(f"[LLM] Model unloaded: {self.model_id}")

    @classmethod
    def unload_all(cls) -> None:
        with cls._lock:
            for key in list(cls._instances.keys()):
                cls._instances[key].unload()
            cls._instances.clear()


def generate_response(messages: List[Dict[str, str]], model_id: Optional[str] = None, **kwargs) -> str:
    manager = LLMManager(model_id=model_id, lazy=False)
    return manager.generate_response(messages, **kwargs)
