import os
import subprocess
import shutil

def check_device_nodes():
    """Check if GPU device nodes are available (WSL2 passthrough)."""
    devices = ["/dev/dxg", "/dev/kfd", "/dev/dri"]
    found = []
    for dev in devices:
        if os.path.exists(dev):
            found.append(dev)
    return found

def check_rocm():
    """Check ROCm installation and GPU visibility."""
    rocminfo = shutil.which("rocminfo")
    if not rocminfo:
        rocm_path = "/opt/rocm/bin/rocminfo"
        if os.path.exists(rocm_path):
            rocminfo = rocm_path

    if not rocminfo:
        return None, "rocminfo not found. ROCm may not be installed."

    try:
        result = subprocess.run([rocminfo], capture_output=True, text=True, timeout=10)
        gpu_lines = [l.strip() for l in result.stdout.splitlines()
                     if 'gfx' in l.lower() or '7900' in l.lower() or 'name:' in l.lower()]
        return gpu_lines, None
    except Exception as e:
        return None, str(e)

def check_torch():
    """Check PyTorch GPU detection."""
    try:
        import torch
        info = {
            "cuda_available": torch.cuda.is_available(),
            "hip_version": getattr(torch.version, 'hip', None),
            "cuda_version": getattr(torch.version, 'cuda', None),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "devices": []
        }
        for i in range(info["device_count"]):
            info["devices"].append(torch.cuda.get_device_name(i))
        return info, None
    except ImportError:
        return None, "PyTorch not installed."
    except Exception as e:
        return None, str(e)

def check_env_vars():
    """Check GPU-related environment variables."""
    keys = ["HSA_OVERRIDE_GFX_VERSION", "HSA_ENABLE_SDMA",
            "LD_LIBRARY_PATH", "ROCM_PATH", "HIP_VISIBLE_DEVICES"]
    return {k: os.environ.get(k, "(not set)") for k in keys}

def diagnose():
    print("=" * 60)
    print("  AMD 7900XT / ROCm GPU Verification")
    print("=" * 60)

    # 1. Device nodes
    print("\n[1] Device Nodes:")
    devices = check_device_nodes()
    if devices:
        for d in devices:
            print(f"  FOUND: {d}")
    else:
        print("  NONE FOUND (/dev/dxg, /dev/kfd, /dev/dri)")
        print("  -> GPU passthrough is not configured.")
        print("  -> If on WSL2, run via docker-compose.yml with device mappings.")

    # 2. ROCm
    print("\n[2] ROCm:")
    gpu_lines, err = check_rocm()
    if err:
        print(f"  ERROR: {err}")
    elif gpu_lines:
        for line in gpu_lines:
            print(f"  {line}")
    else:
        print("  No GPU detected by rocminfo.")

    # 3. PyTorch
    print("\n[3] PyTorch:")
    torch_info, err = check_torch()
    if err:
        print(f"  ERROR: {err}")
    elif torch_info:
        print(f"  CUDA available: {torch_info['cuda_available']}")
        print(f"  HIP version:   {torch_info['hip_version']}")
        print(f"  CUDA version:  {torch_info['cuda_version']}")
        print(f"  Device count:  {torch_info['device_count']}")
        for i, name in enumerate(torch_info['devices']):
            print(f"  Device {i}:     {name}")

    # 4. Env vars
    print("\n[4] Environment Variables:")
    env = check_env_vars()
    for k, v in env.items():
        print(f"  {k} = {v}")

    # 5. Verdict
    print("\n" + "=" * 60)
    is_gpu = (devices and torch_info and torch_info.get("cuda_available"))
    if is_gpu:
        dev_name = torch_info['devices'][0] if torch_info['devices'] else "unknown"
        if 'gfx1100' in str(gpu_lines).lower() or '7900' in dev_name.lower():
            print("  PASS: Running on AMD Radeon 7900XT (gfx1100)")
        else:
            print(f"  PASS: GPU detected ({dev_name}), but may not be 7900XT.")
    else:
        print("  FAIL: No GPU detected.")
        print("")
        print("  To fix, run locally with your WSL2 docker-compose setup:")
        print("    docker compose up -d")
        print("    docker exec -it rocm_scraper python tools/verify_amd_gpu.py")
    print("=" * 60)

if __name__ == "__main__":
    diagnose()
