#!/usr/bin/env python3
import sys
import subprocess

def run_cmd(cmd):
    print(f"[*] Executing: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def main():
    print("================================================================================")
    print(" CROSS-PLATFORM HARDWARE ORCHESTRATION & DEPENDENCY BOOTSTRAPPER")
    print("================================================================================")

    # 1. Detect OS
    is_windows = sys.platform.startswith("win")
    is_linux = sys.platform.startswith("linux")

    # 2. Detect GPU Hardware
    has_nvidia = False
    has_amd = False

    try:
        res = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if res.returncode == 0:
            has_nvidia = True
    except FileNotFoundError:
        pass

    if not has_nvidia:
        # Check AMD
        try:
            res_win = subprocess.run(["rocm-smi"], capture_output=True, text=True)
            if res_win.returncode == 0:
                has_amd = True
        except FileNotFoundError:
            pass

    print(f"[*] Detected OS: {sys.platform}")
    print(f"[*] Detected NVIDIA GPU: {has_nvidia}")
    print(f"[*] Detected AMD GPU: {has_amd}")

    # 3. Formulate Install Path
    print("\n[*] Installing PyTorch Core...")
    if has_nvidia and is_linux:
        # Optimal Linux NVIDIA tier. Upgraded to Nightly cu124 to support Blackwell (sm_120) and Hopper (sm_90)
        run_cmd("python -m pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu124")
    elif has_amd and is_windows:
        # Optimal Windows AMD tier (7900XT)
        run_cmd("python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.1")
    elif has_nvidia and is_windows:
        # Fallback Windows NVIDIA
        run_cmd("python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
    else:
        # Fallback CPU / Mac
        run_cmd("python -m pip install torch torchvision torchaudio")

    print("\n[*] Installing HuggingFace Stack...")
    run_cmd("python -m pip install transformers accelerate sentence-transformers tqdm wheel")

    if has_nvidia and is_linux:
        print("\n[*] Linux + NVIDIA detected: Installing Enterprise FlashAttention-2...")
        try:
            # Requires ninja, wheel, and build tools to be pre-installed on the Linux cluster
            run_cmd("python -m pip install packaging ninja wheel")
            run_cmd("python -m pip install flash-attn --no-build-isolation")
        except Exception as e:
            print(f"[!] Warning: FlashAttention compilation failed. SDPA fallback will be used. ({e})")
            
    print("\n[*] Bootstrapping Local Model Weights...")
    try:
        run_cmd("python bootstrap.py --bootstrap")
    except Exception as e:
        print(f"[!] Warning: Failed to pre-cache models. ({e})")
    
    print("\n[✓] Environment Bootstrapped Successfully.")

if __name__ == "__main__":
    main()
