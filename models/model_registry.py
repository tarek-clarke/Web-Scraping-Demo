"""Process-level shared model instances.

This keeps BERT and Gemma loaded once per Python process and reuses the same
instances across runners, reconcilers, and preflight checks.
"""

from __future__ import annotations

import gc

from pathlib import Path
from typing import Optional

from models.bert_model import BERTModel
from models.gemma_offline import GemmaModel

_BERT_SHARED: dict[bool, BERTModel] = {}
_GEMMA_SHARED: dict[str, GemmaModel] = {}


def get_shared_bert_model(allow_internet: bool = True) -> BERTModel:
    cache_key = bool(allow_internet)
    model = _BERT_SHARED.get(cache_key)
    if model is None:
        model = BERTModel(allow_internet=allow_internet)
        _BERT_SHARED[cache_key] = model
    return model


def get_shared_gemma_model(local_path: Optional[str | Path] = None) -> GemmaModel:
    cache_key = str(Path(local_path).expanduser().resolve()) if local_path else "__default__"
    model = _GEMMA_SHARED.get(cache_key)
    if model is None:
        model = GemmaModel(local_path=local_path)
        _GEMMA_SHARED[cache_key] = model
    return model


def clear_shared_model_cache() -> None:
    """Clear all shared model instances so the next request loads fresh."""

    _BERT_SHARED.clear()
    _GEMMA_SHARED.clear()

    try:
        BERTModel._instance_cache.clear()
    except Exception:
        pass

    try:
        GemmaModel._instance_cache.clear()
    except Exception:
        pass

    gc.collect()

    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            try:
                torch.mps.empty_cache()
            except Exception:
                pass
    except Exception:
        pass
