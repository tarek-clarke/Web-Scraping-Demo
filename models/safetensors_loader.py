"""Windows-safe safetensors loader that bypasses mmap entirely.

On Windows with ROCm, the Rust safetensors mmap implementation crashes
with a hard C++ panic when attempting to read tensor data. This module
provides a pure-Python fallback that reads tensors individually using
standard file seek/read, completely bypassing memory-mapping.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import torch


# Mapping from safetensors dtype strings to (torch dtype, numpy dtype)
# None for numpy dtype means we handle it manually (e.g. bfloat16)
_DTYPE_MAP: dict[str, tuple[torch.dtype, type | None]] = {
    "F64":  (torch.float64,  np.float64),
    "F32":  (torch.float32,  np.float32),
    "F16":  (torch.float16,  np.float16),
    "BF16": (torch.bfloat16, None),       # bfloat16: numpy has no native support
    "I64":  (torch.int64,    np.int64),
    "I32":  (torch.int32,    np.int32),
    "I16":  (torch.int16,    np.int16),
    "I8":   (torch.int8,     np.int8),
    "U8":   (torch.uint8,    np.uint8),
    "BOOL": (torch.bool,     np.bool_),
}


def load_safetensors_no_mmap(
    filepath: str | Path,
    device: str | torch.device = "cpu",
    target_dtype: Optional[torch.dtype] = None,
) -> Dict[str, torch.Tensor]:
    """Load all tensors from a safetensors file without memory-mapping.

    Reads each tensor individually using Python's built-in file seek+read,
    bypassing the Rust mmap implementation that crashes on Windows ROCm.

    Parameters
    ----------
    filepath:
        Path to the .safetensors file.
    device:
        Target device for each tensor (e.g. ``"cpu"``, ``"cuda:0"``).
    target_dtype:
        If set, cast all floating-point tensors to this dtype after loading.

    Returns
    -------
    dict[str, torch.Tensor]
        State dict mapping tensor names to tensors on the target device.
    """
    filepath = Path(filepath)
    state_dict: Dict[str, torch.Tensor] = {}

    with open(filepath, "rb") as f:
        # Parse the safetensors header
        header_size = struct.unpack("<Q", f.read(8))[0]
        header: dict = json.loads(f.read(header_size))

        # Tensor data begins after the 8-byte length prefix + header JSON
        data_offset_base = 8 + header_size

        for name, info in header.items():
            if name == "__metadata__":
                continue

            dtype_str: str = info["dtype"]
            shape: list = info["shape"]
            start, end = info["data_offsets"]

            if dtype_str not in _DTYPE_MAP:
                raise ValueError(
                    f"Unsupported safetensors dtype '{dtype_str}' for tensor '{name}'"
                )

            torch_dtype, np_dtype = _DTYPE_MAP[dtype_str]
            num_bytes = end - start

            f.seek(data_offset_base + start)
            raw = f.read(num_bytes)

            if dtype_str == "BF16":
                # numpy has no bfloat16; read as uint16 and reinterpret
                arr = np.frombuffer(raw, dtype=np.uint16)
                if shape:
                    arr = arr.reshape(shape)
                tensor = torch.from_numpy(arr.copy()).view(torch.bfloat16)
            else:
                arr = np.frombuffer(raw, dtype=np_dtype)
                if shape:
                    arr = arr.reshape(shape)
                tensor = torch.from_numpy(arr.copy())

            # Optionally cast floating-point tensors to a target dtype
            if target_dtype is not None and tensor.is_floating_point():
                tensor = tensor.to(target_dtype)

            state_dict[name] = tensor.to(device)

    return state_dict


__all__ = ["load_safetensors_no_mmap"]
