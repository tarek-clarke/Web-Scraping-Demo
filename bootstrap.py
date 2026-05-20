import os
import sys
import time
import json
import socket
import platform
import subprocess
import importlib.util
import importlib.metadata

def detect_cloud_platform():
    """
    Detects cloud platform based on environment variables or metadata paths.
    """
    # 1. vast.ai -> VAST_CONTAINER or /etc/vastai
    if os.getenv("VAST_CONTAINER") or os.path.exists("/etc/vastai") or os.getenv("VAST_CONTAINERLABEL") or os.getenv("VAST_API_KEY"):
        return "vast.ai"
    # 2. runpod -> RUNPOD_POD_ID
    if os.getenv("RUNPOD_POD_ID") or os.getenv("RUNPOD_API_KEY"):
        return "runpod"
    # 3. lambda -> LAMBDA_TASK_ROOT or /etc/lambda-instance
    if os.getenv("LAMBDA_TASK_ROOT") or os.path.exists("/etc/lambda-instance") or os.getenv("LAMBDA_API_KEY") or os.path.exists("/etc/lambda-login-service"):
        return "lambda"
    # 4. spheron -> SPHERON env
    if os.getenv("SPHERON") or os.getenv("SPHERON_PORT") or any(k.startswith("SPHERON_") for k in os.environ):
        return "spheron"
    
    # 5. lumi -> hostname contains "lumi"
    hostname = socket.gethostname().lower()
    if "lumi" in hostname or any("lumi" in k.lower() for k in os.environ):
        return "lumi"
    # 6. taltech_hpc -> SLURM env or hostname
    if any(k.startswith("SLURM_") for k in os.environ) or "taltech" in hostname or "hpc" in hostname or any("taltech" in k.lower() for k in os.environ):
        return "taltech_hpc"
    
    return "unknown"

def detect_hardware_backend():
    """
    Detects hardware backend using system checks.
    """
    system = platform.system()
    machine = platform.machine().lower()
    processor = platform.processor().lower()
    
    # Try importing torch to inspect hardware directly if available
    try:
        import torch
        if torch.cuda.is_available():
            if hasattr(torch.version, "hip") and torch.version.hip is not None:
                return "AMD ROCm"
            return "NVIDIA CUDA"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "Apple Silicon MPS"
        elif hasattr(torch, "xpu") and torch.xpu.is_available():
            return "Intel GPU"
    except ImportError:
        pass
        
    # Fallback to system-level check without PyTorch
    # NVIDIA CUDA check
    try:
        import shutil
        if shutil.which("nvidia-smi"):
            return "NVIDIA CUDA"
    except Exception:
        pass
    if os.path.exists("/usr/local/cuda") or os.path.exists("/usr/bin/nvcc"):
        return "NVIDIA CUDA"
        
    # AMD ROCm check
    try:
        import shutil
        if shutil.which("rocm-smi") or shutil.which("rocminfo"):
            return "AMD ROCm"
    except Exception:
        pass
    if os.path.exists("/opt/rocm"):
        return "AMD ROCm"
        
    # Intel GPU check
    try:
        import shutil
        if shutil.which("sycl-ls") or shutil.which("intel-smi"):
            return "Intel GPU"
    except Exception:
        pass
        
    # Apple Silicon MPS check
    if system == "Darwin" and ("arm" in machine or "apple" in processor):
        return "Apple Silicon MPS"
        
    return "CPU fallback"

def is_library_installed(lib_name):
    """
    Checks if a package is installed in the python environment.
    """
    try:
        importlib.metadata.version(lib_name)
        return True
    except importlib.metadata.PackageNotFoundError:
        # Check standard import name
        try:
            __import__(lib_name.replace("-", "_"))
            return True
        except ImportError:
            return False

def install_pytorch(hardware):
    """
    Installs the correct PyTorch wheel avoiding source builds.
    """
    # Check if torch is already installed and matches the hardware
    torch_installed = False
    try:
        import torch
        if hardware == "NVIDIA CUDA" and torch.cuda.is_available() and (not hasattr(torch.version, "hip") or torch.version.hip is None):
            torch_installed = True
        elif hardware == "AMD ROCm" and torch.cuda.is_available() and hasattr(torch.version, "hip") and torch.version.hip is not None:
            torch_installed = True
        elif hardware == "Apple Silicon MPS" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            torch_installed = True
        elif hardware == "Intel GPU" and hasattr(torch, "xpu") and torch.xpu.is_available():
            torch_installed = True
        elif hardware == "CPU fallback":
            torch_installed = True
    except ImportError:
        pass

    if torch_installed:
        print(f"[Bootstrap] PyTorch is already installed and compatible with hardware backend: {hardware}")
        return False # Not freshly installed

    print(f"[Bootstrap] PyTorch not found or incompatible. Installing correct build for hardware: {hardware}...")
    
    # Standard index-urls
    cuda_url = "https://download.pytorch.org/whl/cu121"
    rocm_url = "https://download.pytorch.org/whl/rocm6.0"
    cpu_url = "https://download.pytorch.org/whl/cpu"
    
    cmd = [sys.executable, "-m", "pip", "install", "--prefer-binary"]
    
    if hardware == "NVIDIA CUDA":
        cmd.extend(["torch", "torchvision", "torchaudio", "--index-url", cuda_url])
    elif hardware == "AMD ROCm":
        cmd.extend(["torch", "torchvision", "torchaudio", "--index-url", rocm_url])
    elif hardware == "Intel GPU":
        # Intel GPU often uses CPU torch base + IPEX or standard CPU torch
        cmd.extend(["torch", "torchvision", "torchaudio", "--index-url", cpu_url])
    elif hardware == "Apple Silicon MPS":
        # Standard wheels on macOS support MPS natively
        cmd.extend(["torch", "torchvision", "torchaudio"])
    else: # CPU fallback
        cmd.extend(["torch", "torchvision", "torchaudio", "--index-url", cpu_url])
        
    print(f"[Bootstrap] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    if hardware == "Intel GPU":
        # Install Intel Extension for PyTorch
        try:
            print("[Bootstrap] Installing Intel IPEX Extension for PyTorch XPU support...")
            subprocess.run([sys.executable, "-m", "pip", "install", "--prefer-binary", "intel-extension-for-pytorch"], check=True)
        except Exception as e:
            print(f"[Bootstrap] Warning: Intel IPEX installation failed ({e}). Fallback to CPU torch model execution.")
            
    return True

def install_required_libraries(hardware):
    """
    Installs other required libraries if missing, avoiding source builds.
    """
    packages = ["pybind11", "sentence-transformers", "transformers", "accelerate", "optimum", "numpy", "pandas", "scipy", "httpx"]
    
    # Check what is missing
    missing = [pkg for pkg in packages if not is_library_installed(pkg)]
    
    gpu_available = hardware in ["NVIDIA CUDA", "AMD ROCm"]
    
    if gpu_available:
        if not is_library_installed("vllm"):
            missing.append("vllm")
    elif hardware == "CPU fallback":
        if not is_library_installed("llama-cpp-python"):
            missing.append("llama-cpp-python")
            
    if not missing:
        print("[Bootstrap] All library dependencies are already installed.")
        return False # No fresh installs needed
        
    print(f"[Bootstrap] Installing missing dependencies: {missing}...")
    # Add --prefer-binary and --only-binary to avoid slow source compilations
    cmd = [sys.executable, "-m", "pip", "install", "--prefer-binary", "--only-binary=:all:"]
    cmd.extend(missing)
    
    # Try running the install. If it fails, fallback without strict only-binary for compatible wheels
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print("[Bootstrap] Warning: only-binary install failed, trying regular pip install with --prefer-binary...")
        cmd_fallback = [sys.executable, "-m", "pip", "install", "--prefer-binary"]
        cmd_fallback.extend(missing)
        subprocess.run(cmd_fallback, check=True)
        
    return True

def build_cpp_extension():
    """
    Builds the C++ acceleration layer (cpp_accel) inplace using pybind11.
    """
    print("[Bootstrap] Building C++ acceleration layer (cpp_accel)...")
    cmd = [sys.executable, "setup.py", "build_ext", "--inplace"]
    print(f"[Bootstrap] Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("[Bootstrap] C++ acceleration layer built successfully.")
        return True
    except Exception as e:
        print(f"[Bootstrap] Error building C++ acceleration layer: {e}")
        return False

def cache_model_weights():
    """
    Pre-caches the model weights locally.
    """
    print("[Bootstrap] Caching model weights...")
    
    # 1. MiniLM
    try:
        print("[Bootstrap] Downloading sentence-transformers/all-MiniLM-L6-v2...")
        from transformers import AutoTokenizer, AutoModel
        AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        print("[Bootstrap] all-MiniLM-L6-v2 successfully cached.")
    except Exception as e:
        print(f"[Bootstrap] Warning: Failed to pre-cache MiniLM ({e}).")

    # 2. Gemma-4 E4B
    try:
        from models.gemma_local import GemmaLocal
        from transformers import AutoModelForCausalLM, AutoTokenizer

        gemma_repo_id = "google/gemma-4-E4B"

        gemma_local_path = GemmaLocal.discover_local_path()

        if gemma_local_path is None:
            print(f"[Bootstrap] Downloading {gemma_repo_id} into the local Hugging Face cache...")
            AutoTokenizer.from_pretrained(gemma_repo_id)
            AutoModelForCausalLM.from_pretrained(gemma_repo_id)
            gemma_local_path = GemmaLocal.discover_local_path()

        if gemma_local_path is None:
            raise FileNotFoundError(
                f"Gemma checkpoint could not be discovered after downloading {gemma_repo_id}."
            )

        print(f"[Bootstrap] Validating local Gemma checkpoint at {gemma_local_path}...")
        AutoTokenizer.from_pretrained(gemma_local_path, local_files_only=True)
        AutoModelForCausalLM.from_pretrained(gemma_local_path, local_files_only=True)
        print("[Bootstrap] Local Gemma checkpoint validated and cached.")
    except Exception as e:
        print(f"[Bootstrap] Warning: local Gemma checkpoint validation failed ({e}).")

def run_bootstrap(force=False):
    """
    Runs the initialization process.
    """
    if os.path.exists(".initialized") and not force:
        print("[Bootstrap] Already initialized. Skipping bootstrap phase. Use --bootstrap to force.")
        return
        
    start_time = time.perf_counter()
    print("\n" + "="*80)
    print(" BOOTSTRAP INITIALIZATION: FAST CLOUD-OPTIMIZED LAUNCH")
    print("="*80 + "\n")
    
    # 1. Cloud & Hardware Detection
    cloud = detect_cloud_platform()
    hardware = detect_hardware_backend()
    
    print(f"[Bootstrap] Cloud Environment Detected : {cloud.upper()}")
    print(f"[Bootstrap] Hardware Backend Detected  : {hardware.upper()}")
    
    # 2. Install PyTorch
    torch_fresh = install_pytorch(hardware)
    
    # 3. Install remaining libraries
    libs_fresh = install_required_libraries(hardware)
    
    # 4. Build C++ acceleration layer
    cpp_built = False
    try:
        import cpp_accel
        print("[Bootstrap] C++ acceleration layer (cpp_accel) is already importable.")
    except ImportError:
        cpp_built = build_cpp_extension()
    
    # 5. Cache weights
    cache_model_weights()
    
    duration = time.perf_counter() - start_time
    fresh_install = torch_fresh or libs_fresh or cpp_built
    
    # 5. Write initialization token file
    init_data = {
        "initialized": True,
        "cloud_platform": cloud,
        "hardware_backend": hardware,
        "bootstrap_duration_sec": round(duration, 2),
        "fresh_install": fresh_install,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    with open(".initialized", "w") as f:
        json.dump(init_data, f, indent=2)
        
    print("\n" + "="*80)
    print(" INITIALIZATION LOG REPORT")
    print("-"*80)
    print(f" Cloud Platform                 : {cloud}")
    print(f" Hardware Backend                : {hardware}")
    print(f" Bootstrap Duration              : {duration:.2f} seconds")
    print(f" Fresh Dependencies Installed    : {fresh_install}")
    print("="*80 + "\n")

if __name__ == "__main__":
    # If run as script
    force_boot = "--bootstrap" in sys.argv
    run_bootstrap(force=force_boot)
