import os
import platform
import socket
import subprocess
import psutil


def _normalize_gpu_name(value):
    if not value:
        return None
    cleaned = value.strip()
    prefixes = ["NVIDIA GeForce ", "NVIDIA "]
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    return cleaned or None


def _format_vram_gb(total_bytes):
    if not total_bytes:
        return None
    return int(round(total_bytes / (1024 ** 3)))


def _normalize_cpu_name(value):
    if not value:
        return "CPU"
    lowered = value.strip().lower()
    if lowered in {"x86_64", "amd64", "i386", "i686", "intel64", "generic cpu", ""}:
        return "CPU"
    return value.strip()


def _query_nvidia_gpu_info():
    """Return the first NVIDIA GPU name and VRAM in GB from nvidia-smi, if available."""
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ]
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        if not output:
            return None, None
        first_line = output.splitlines()[0]
        parts = [part.strip() for part in first_line.split(",")]
        gpu_name = _normalize_gpu_name(parts[0] if parts else None)
        vram_gb = None
        if len(parts) > 1:
            try:
                vram_gb = int(round(float(parts[1]) / 1024.0))
            except Exception:
                vram_gb = None
        return gpu_name, vram_gb
    except Exception:
        return None, None


def _query_motherboard_info():
    """Return motherboard name and BIOS info from dmidecode, if available."""
    try:
        cmd = ["dmidecode", "-s", "baseboard-product-name"]
        motherboard = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        if not motherboard:
            motherboard = None
        return motherboard
    except Exception:
        return None

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
    
    # ── Apple Silicon MPS check (primary system check, before PyTorch)
    if system == "Darwin" and ("arm" in machine or "apple" in processor):
        return "Apple Silicon MPS"
    
    # Try importing torch to inspect other hardware backends
    try:
        import torch
        torch_cuda = getattr(torch, "cuda", None)
        # NVIDIA CUDA or AMD ROCm (via HIP)
        if torch_cuda is not None and hasattr(torch_cuda, "is_available") and torch_cuda.is_available():
            # Check if it's actually AMD ROCm via HIP
            if hasattr(torch.version, 'hip') and torch.version.hip is not None:
                return "AMD ROCm"
            return "NVIDIA CUDA"
        # Intel GPU (XPU)
        if hasattr(torch, 'xpu') and torch.xpu.is_available():
            return "Intel GPU"
    except Exception:
        pass
        
    # Fallback to system-level checks without PyTorch
    # NVIDIA CUDA check
    try:
        import shutil
        if shutil.which("nvidia-smi"):
            return "NVIDIA CUDA"
    except Exception:
        pass
    if os.path.exists("/usr/local/cuda") or os.path.exists("/usr/bin/nvcc"):
        return "NVIDIA CUDA"
        
    # AMD ROCm check (Linux-style paths)
    try:
        import shutil
        if shutil.which("rocm-smi") or shutil.which("rocminfo"):
            return "AMD ROCm"
    except Exception:
        pass
    if os.path.exists("/opt/rocm"):
        return "AMD ROCm"
    
    # AMD ROCm/HIP check (Windows-style paths)
    if system == "Windows":
        try:
            import shutil
            # Check for HIP on Windows
            if shutil.which("hipinfo") or shutil.which("hip-smi"):
                return "AMD ROCm"
            # Check for HIP in common Windows install paths
            rocm_paths = [
                "C:\\Program Files\\AMD\\ROCm\\bin",
                "C:\\rocm\\bin",
                "C:\\Program Files (x86)\\AMD\\ROCm\\bin"
            ]
            for path in rocm_paths:
                if os.path.exists(os.path.join(path, "hipinfo.exe")) or \
                   os.path.exists(os.path.join(path, "hip-smi.exe")):
                    return "AMD ROCm"
        except Exception:
            pass
        
    # Intel GPU check
    try:
        import shutil
        if shutil.which("sycl-ls") or shutil.which("intel-smi"):
            return "Intel GPU"
    except Exception:
        pass
        
    return "CPU fallback"

def get_device_info():
    """
    Detects hardware platform (CUDA, ROCm, MPS, CPU), GPU model, and cloud platform.
    Returns:
        dict: {
            "device": str ("cuda" | "rocm" | "mps" | "cpu"),
            "model": str (e.g., "RTX_5090", "7900XT", "M4", "Intel Core i7"),
            "cpu_name": str (e.g., "Intel Core i7-13700K"),
            "cpu_cores": int,
            "ram_gb": int (total system RAM in GB),
            "motherboard": str (e.g., "ASUS ROG Maximus Z790"),
            "os_name": str (e.g., "Linux"),
            "os_version": str (e.g., "5.15.0-1234"),
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

    # ── CPU info ──
    cpu_name = "Unknown CPU"
    cpu_cores = 1
    ram_gb = 0
    try:
        cpu_name = platform.processor() or "Unknown CPU"
        cpu_cores = os.cpu_count() or 1
        ram_bytes = psutil.virtual_memory().total
        ram_gb = int(round(ram_bytes / (1024 ** 3)))
    except Exception:
        pass

    # ── Motherboard and OS info ──
    motherboard = _query_motherboard_info() or "Unknown"
    os_name = platform.system()
    os_version = platform.release()
        
    # Attempt to query model name
    model = "CPU"
    gpu_name = None
    vram_gb = None
    try:
        import torch
        if device in ["cuda", "rocm"] and torch.cuda.is_available():
            nvidia_name, nvidia_vram = _query_nvidia_gpu_info()
            try:
                gpu_name = torch.cuda.get_device_name(0).strip()
            except Exception:
                gpu_name = "GPU"
            try:
                props = torch.cuda.get_device_properties(0)
                vram_gb = _format_vram_gb(getattr(props, "total_memory", None))
            except Exception:
                vram_gb = None
            if nvidia_name:
                gpu_name = nvidia_name
            if nvidia_vram is not None:
                vram_gb = nvidia_vram
            model = gpu_name or "GPU"
            if vram_gb:
                model = f"{model} ({vram_gb}GB)"
        elif device == "mps":
            model = f"Apple Silicon ({platform.processor() or 'arm64'})"
        else:
            model = _normalize_cpu_name(platform.processor() or platform.machine() or "CPU")
    except ImportError:
        if platform.system() == "Darwin":
            model = "Apple Silicon GPU"
        else:
            model = _normalize_cpu_name(platform.processor() or "CPU")
            
    return {
        "device": device,
        "model": model,
        "cloud": cloud,
        "hardware_backend": hardware_backend,
        "gpu_name": gpu_name,
        "vram_gb": vram_gb,
        "cpu_name": cpu_name,
        "cpu_cores": cpu_cores,
        "ram_gb": ram_gb,
        "motherboard": motherboard,
        "os_name": os_name,
        "os_version": os_version
    }
