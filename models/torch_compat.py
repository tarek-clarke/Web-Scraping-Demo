"""Compatibility helpers for PyTorch/Transformers on Windows ROCm wheels."""

from __future__ import annotations

import sys
import types


def ensure_transformers_import_compatibility() -> None:
    """Stub unsupported distributed-tensor imports that recent transformers may touch."""

    try:
        import torch  # noqa: F401

        try:
            import torch.distributed.tensor.device_mesh  # noqa: F401
            return
        except Exception:
            pass
    except Exception:
        return

    tensor_pkg = types.ModuleType("torch.distributed.tensor")
    tensor_pkg.__path__ = []
    sys.modules["torch.distributed.tensor"] = tensor_pkg

    for name in ["parallel", "_ops", "placement_types", "_dtensor_spec"]:
        sys.modules["torch.distributed.tensor." + name] = types.ModuleType(
            "torch.distributed.tensor." + name
        )

    device_mesh_module = types.ModuleType("torch.distributed.tensor.device_mesh")
    device_mesh_module.DeviceMesh = type("DeviceMesh", (), {})
    sys.modules["torch.distributed.tensor.device_mesh"] = device_mesh_module
