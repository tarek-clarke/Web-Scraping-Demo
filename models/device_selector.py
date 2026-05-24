import os
import platform
import socket

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
    
    return "local" # Default to local if not cloud

def detect_hardware_backend():
    """
    Detects hardware backend using system checks.
    Returns one of:
        "NVIDIA CUDA"
        "AMD ROCm"
        "Intel GPU"
        "Apple Silicon MPS"
        "CPU fallback"
    """
    system = platform.system()
    machine = platform.machine().lower()
    processor = platform.processor().lower()
    
    # Try importing torch to inspect hardware directly if available
    try:
        import torch
        # NVIDIA CUDA
        if torch.cuda.is_available():
            # Check if it's actually AMD ROCm via HIP
            if hasattr(torch.version, 'hip') and torch.version.hip is not None:
                return "AMD ROCm"
            return "NVIDIA CUDA"
        # Apple Silicon MPS
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "Apple Silicon MPS"
        # Intel GPU (XPU)
        if hasattr(torch, 'xpu') and torch.xpu.is_available():
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

def get_device_info():
    """
    Detects hardware platform (CUDA, ROCm, MPS, CPU), GPU model, and cloud platform.
    Returns:
        dict: {
            "device": str ("cuda" | "rocm" | "mps" | "cpu"),
            "model": str (e.g., "RTX_5090", "7900XT", "M4", "Intel Core i7"),
            "cloud": str ("vast.ai" | "runpod" | "lambda" | "spheron" | "lumi" | "taltech_hpc" | "local" | "unknown"),
            "hardware_backend": str ("NVIDIA CUDA" | "AMD ROCm" | "Intel GPU" | "Apple Silicon MPS" | "CPU fallback")
        }
    """
    cloud = detect_cloud_platform()
    hardware_backend = detect_hardware_backend()
    
    # Map to standard lower-case device identifier for torch integration in the codebase
    device = "cpu"
    if hardware_backend == "NVIDIA CUDA":
        device = "cuda"
    elif hardware_backend == "AMD ROCm":
        device = "rocm"
    elif hardware_backend == "Apple Silicon MPS":
        device = "mps"
    elif hardware_backend == "Intel GPU":
        device = "cpu" # IPEX fits cpu model runs or torch CPU backend fallback
        
    # Attempt to query model name
    model = "Generic CPU"
    try:
        import torch
        if device in ["cuda", "rocm"] and torch.cuda.is_available():
            try:
                model = torch.cuda.get_device_name(0)
            except Exception:
                model = "NVIDIA/AMD GPU"
        elif device == "mps":
            model = f"Apple Silicon ({platform.processor() or 'arm64'})"
        else:
            model = platform.processor() or platform.machine() or "Intel/AMD CPU"
    except ImportError:
        if platform.system() == "Darwin":
            model = "Apple Silicon GPU"
        else:
            model = platform.processor() or "Generic CPU"
            
    return {
        "device": device,
        "model": model,
        "cloud": cloud,
        "hardware_backend": hardware_backend
    }
