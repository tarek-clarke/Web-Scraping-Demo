"""Compatibility helpers for the vendor Sentence Transformers runtime."""

from __future__ import annotations


def install_hub_compat() -> None:
    """Restore the legacy Hub symbol expected by some Transformers releases."""
    try:
        import huggingface_hub
    except ImportError:
        return
    if hasattr(huggingface_hub, "is_offline_mode"):
        return
    try:
        from huggingface_hub.constants import HF_HUB_OFFLINE
    except ImportError:
        HF_HUB_OFFLINE = False
    huggingface_hub.is_offline_mode = lambda: bool(HF_HUB_OFFLINE)
