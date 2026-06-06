import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InferenceConfig:
    model_id: str = field(
        default_factory=lambda: os.environ.get("HF_MODEL_ID", "google/gemma-4-E4B-it")
    )
    hf_token: Optional[str] = field(
        default_factory=lambda: os.environ.get("HF_TOKEN", None)
    )
    max_reasoning_tokens: int = field(
        default_factory=lambda: int(os.environ.get("LLM_MAX_REASONING_TOKENS", "2048"))
    )
    device_map: str = field(
        default_factory=lambda: os.environ.get("HF_DEVICE_MAP", "auto")
    )
    torch_dtype: str = field(
        default_factory=lambda: os.environ.get("HF_TORCH_DTYPE", "auto")
    )
    attn_implementation: str = field(
        default_factory=lambda: os.environ.get("HF_ATTN_IMPL", "auto")
    )
    load_in_4bit: bool = field(
        default_factory=lambda: os.environ.get("HF_LOAD_4BIT", "").lower() in ("1", "true", "yes")
    )
    load_in_8bit: bool = field(
        default_factory=lambda: os.environ.get("HF_LOAD_8BIT", "").lower() in ("1", "true", "yes")
    )
    local_model_path: Optional[str] = field(
        default_factory=lambda: os.environ.get("HF_LOCAL_MODEL_PATH", None)
    )
