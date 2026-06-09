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
import re
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

# Allow FORCE_CPU=1 to build a CPU-only extension even when ROCm/CUDA headers
# are detected.  Useful inside containers where the SDK is incomplete or the
# GPU hardware is not accessible (e.g. WSL2 with AMD ROCm).
FORCE_CPU: bool = os.environ.get("FORCE_CPU", "0") == "1"

def _mps_available() -> bool:
    backends = getattr(torch, "backends", None)
    mps_backend = getattr(backends, "mps", None) if backends is not None else None
    return bool(mps_backend and hasattr(mps_backend, "is_available") and mps_backend.is_available())


def _detect_backend() -> str:
    if FORCE_CPU:
        return "cpu"
    if getattr(torch.version, "hip", None) is not None:
        return "rocm"
    if CUDA_HOME is not None or torch.cuda.is_available():
        return "cuda"
    if _mps_available():
        return "mps"
    return "cpu"


def _cuda_arch_flags_from_list(arch_list: str) -> list[str]:
    flags: list[str] = []
    for token in re.split(r"[;,\s]+", arch_list or ""):
        token = token.strip()
        if not token:
            continue

        cleaned = token.replace("+PTX", "").replace("+ptx", "")
        match = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:[a-z])?", cleaned)
        if not match:
            continue

        major = match.group(1)
        minor = match.group(2) or "0"
        sm = f"{major}{minor}"
        flags.append(f"--generate-code=arch=compute_{sm},code=sm_{sm}")

    return flags


BUILD_BACKEND = _detect_backend()
IS_ROCM: bool = BUILD_BACKEND == "rocm"
IS_CUDA: bool = BUILD_BACKEND == "cuda"
IS_MPS: bool = BUILD_BACKEND == "mps"

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
elif IS_MPS:
    print("[fast_ingest/setup.py] Backend: Apple Silicon MPS  "
          "(building CPU-compatible extension stub)", flush=True)
else:
    print("[fast_ingest/setup.py] WARNING: No GPU backend detected — "
          "building CPU-only stub (no pinned-memory / stream support).",
          flush=True)

# ---------------------------------------------------------------------------
# Compiler flags
# ---------------------------------------------------------------------------

# ── Host (C++) flags ────────────────────────────────────────────────────────
import platform
CXX_FLAGS = ["-std=c++17", "-O3"]
if platform.system() != "Windows":
    CXX_FLAGS += [
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
        "-D__HIP_PLATFORM_AMD__",
        "-O3",
        "--use_fast_math",
        # Enable HIP stream priority for p99 latency reduction
        "-DHIP_STREAM_PRIORITY_ENABLED",
        # Verbose compilation helps diagnose HIP kernel registration issues.
        # Comment out in CI to reduce noise.
        # "-v",
    ]
elif IS_CUDA:
    env_arch_list = os.environ.get("TORCH_CUDA_ARCH_LIST", "").strip()
    arch_flags = _cuda_arch_flags_from_list(env_arch_list)
    if not arch_flags:
        arch_flags = [
            "--generate-code=arch=compute_89,code=sm_89",   # L40 / RTX 4090 (Ada)
            "--generate-code=arch=compute_80,code=sm_80",   # A100 (Ampere)
            "--generate-code=arch=compute_90,code=sm_90",   # H100 / H200 (Hopper)
        ]

    NVCC_FLAGS = ["-O3", "--use_fast_math"] + arch_flags
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

# Automatically find PyTorch NVIDIA wheel headers (e.g., cusparse.h) for pip-only environments
import glob
PYTORCH_NVIDIA_INCLUDES = []
try:
    site_packages = Path(torch.__file__).parent.parent
    nvidia_dir = site_packages / "nvidia"
    if nvidia_dir.is_dir():
        for inc_dir in nvidia_dir.glob("*/include"):
            if inc_dir.is_dir():
                PYTORCH_NVIDIA_INCLUDES.append(str(inc_dir))
except Exception:
    pass

if IS_ROCM or IS_CUDA:
    RPATH_ARGS = [
        f"-Wl,-rpath,{TORCH_LIB_PATH}",
        f"-Wl,-rpath,{ROCM_LIB_PATH}" if IS_ROCM else "",
    ]
    ext = CUDAExtension(
        name="fast_ingest",
        sources=SOURCES,
        include_dirs=PYTORCH_NVIDIA_INCLUDES,
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
    cpu_flags = CXX_FLAGS + ["-DFAST_INGEST_CPU_ONLY"]
    ext = CppExtension(
        name="fast_ingest",
        sources=SOURCES,
        extra_compile_args={"cxx": cpu_flags},
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
