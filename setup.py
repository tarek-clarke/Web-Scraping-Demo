"""
setup.py — Build script for the fast_ingest C++ PyTorch Extension.

Compiles fast_ingest.cpp into a Python-importable shared library using
PyTorch's CppExtension / CUDAExtension build helpers.  The script
auto-detects whether the host is a ROCm/HIP environment or a CUDA
environment and sets the appropriate architecture / optimisation flags.

Usage
-----
# Development build (in-place, no install):
    python setup.py build_ext --inplace

# System/venv install:
    pip install .  (or)  python setup.py install

The resulting module can be imported as:
    import fast_ingest
    t = fast_ingest.normalize(packet, lo, hi)

Requirements
------------
  • PyTorch ≥ 2.0 with ROCm (HIP) or CUDA support
  • For ROCm: ROCm ≥ 5.0 (tested on 6.2), AMD clang ≥ 17
  • For CUDA: CUDA ≥ 11.3, gcc/g++ ≥ 9
  • C++17 compiler (enforced via -std=c++17)

Copyright (c) 2026 Tarek Clarke. All rights reserved.
Licensed under the PolyForm Noncommercial License 1.0.0.
"""

import os
import sys
from pathlib import Path

import torch
from torch.utils.cpp_extension import (
    CppExtension,
    CUDAExtension,
    BuildExtension,
    CUDA_HOME,
)
from setuptools import setup

# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

IS_ROCM: bool = getattr(torch.version, "hip", None) is not None
IS_CUDA: bool = (not IS_ROCM) and (CUDA_HOME is not None or
                                    torch.cuda.is_available())

ROCM_PATH: str = os.environ.get("ROCM_PATH", "/opt/rocm")

# RPATH: embed the absolute path to libc10/libtorch in the .so so the extension
# can be imported without setting LD_LIBRARY_PATH.  Always import torch before
# fast_ingest in Python (translator.py does this already).
TORCH_LIB_PATH: str = str(Path(torch.__file__).parent / "lib")
ROCM_LIB_PATH: str = os.path.join(ROCM_PATH, "lib")

print(f"[fast_ingest/setup.py] torch {torch.__version__}", flush=True)
if IS_ROCM:
    print(f"[fast_ingest/setup.py] Backend: ROCm/HIP  "
          f"({torch.version.hip})  ROCM_PATH={ROCM_PATH}", flush=True)
elif IS_CUDA:
    print(f"[fast_ingest/setup.py] Backend: CUDA  "
          f"({torch.version.cuda})  CUDA_HOME={CUDA_HOME}", flush=True)
else:
    print("[fast_ingest/setup.py] WARNING: No GPU backend detected — "
          "building CPU-only stub (no pinned-memory / stream support).",
          flush=True)

# ---------------------------------------------------------------------------
# Compiler flags
# ---------------------------------------------------------------------------

# ── Host (C++) flags ────────────────────────────────────────────────────────
CXX_FLAGS = [
    "-std=c++17",       # required for <string_view>, if-constexpr, structured bindings
    "-O3",              # full optimisation
    "-fPIC",            # position-independent code (shared library)
    "-Wall",
    "-Wextra",
    "-Wno-unused-parameter",  # pybind11 stubs trigger this
]

if IS_ROCM:
    # ROCm/HIP uses the AMD clang host compiler. These flags are compatible.
    CXX_FLAGS += [
        "-D__HIP_PLATFORM_AMD__",   # explicit HIP platform guard
    ]

# ── Device (HIP/NVCC) flags ─────────────────────────────────────────────────
# In ROCm builds, PyTorch's BuildExtension routes nvcc → hipcc.
# RDNA3 architecture (RX 7900 XT): gfx1100
# Common CDNA targets for datacenter GPUs: gfx90a (MI250X), gfx940 (MI300X)

if IS_ROCM:
    # The ROCm offload-arch flag targets the physical GPU present in this
    # machine.  Add more --offload-arch entries for multi-GPU portability.
    NVCC_FLAGS = [
        "--offload-arch=gfx1100",   # AMD Radeon RX 7900 XT (RDNA3 / gfx1100)
        "--offload-arch=gfx90a",    # MI250X (optional, no-op if absent)
        "-O3",
        "--use_fast_math",
        # Verbose compilation helps diagnose HIP kernel registration issues.
        # Comment out in CI to reduce noise.
        # "-v",
    ]
elif IS_CUDA:
    NVCC_FLAGS = [
        "-O3",
        "--use_fast_math",
        # Modern Ampere / Ada Lovelace (adjust for your target GPU)
        "--generate-code=arch=compute_89,code=sm_89",  # RTX 40xx (Ada)
        "--generate-code=arch=compute_86,code=sm_86",  # RTX 30xx (Ampere)
        "--generate-code=arch=compute_75,code=sm_75",  # RTX 20xx (Turing)
        "--generate-code=arch=compute_70,code=sm_70",  # V100
        "--generate-code=arch=compute_80,code=sm_80",  # A100
    ]
else:
    NVCC_FLAGS = []

# ---------------------------------------------------------------------------
# Extension definition
# ---------------------------------------------------------------------------

SOURCES = [str(Path(__file__).parent / "fast_ingest.cpp")]

EXTRA_COMPILE_ARGS = {
    "cxx": CXX_FLAGS,
    "nvcc": NVCC_FLAGS,
}

if IS_ROCM or IS_CUDA:
    RPATH_ARGS = [
        f"-Wl,-rpath,{TORCH_LIB_PATH}",
        f"-Wl,-rpath,{ROCM_LIB_PATH}" if IS_ROCM else "",
    ]
    ext = CUDAExtension(
        name="fast_ingest",
        sources=SOURCES,
        extra_compile_args=EXTRA_COMPILE_ARGS,
        extra_link_args=[a for a in RPATH_ARGS if a],
        # PyTorch's CUDAExtension automatically adds:
        #   - torch include paths   (libtorch)
        #   - ROCm/CUDA include paths
        #   - Python.h include
        #   - Required libs: c10, c10_cuda, torch, torch_python
    )
else:
    # CPU-only fallback: pinned-memory and stream calls are stubbed out in the
    # extension by the conditional compilation macros in fast_ingest.cpp.
    ext = CppExtension(
        name="fast_ingest",
        sources=SOURCES,
        extra_compile_args={"cxx": CXX_FLAGS},
    )

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup(
    name="fast_ingest",
    version="1.0.0",
    description=(
        "Zero-copy C++ PyTorch extension for F1 telemetry ingestion — "
        "AMD ROCm / NVIDIA CUDA"
    ),
    long_description=__doc__,
    author="Tarek Clarke",
    license="PolyForm Noncommercial License 1.0.0",

    # The extension module is the ONLY deliverable; no Python packages.
    py_modules=[],
    ext_modules=[ext],

    # BuildExtension handles:
    #   • Switching nvcc→hipcc on ROCm
    #   • Injecting -DTORCH_EXTENSION_NAME=fast_ingest
    #   • Locating Python.h / torch headers
    cmdclass={"build_ext": BuildExtension.with_options(no_python_abi_suffix=False)},

    python_requires=">=3.9",
    install_requires=[
        # Only the major.minor version is required to avoid local-label issues
        # (e.g. 2.3.0a0+git96dd291 is not a valid PEP 440 install_requires spec).
        "torch>=2.0",
    ],
    zip_safe=False,
)
