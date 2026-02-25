# Quick Start: Windows AMD 7900 XT Setup

This directory contains automated scripts to set up the Resilient RAP Framework with HIP SDK for Windows GPU acceleration.

## TL;DR (5 minutes)

```powershell
# 1. Install prerequisites (one-time)
#    - Visual Studio Build Tools 2022 from https://visualstudio.microsoft.com/downloads/
#    - HIP SDK for Windows from https://rocm.docs.amd.com/projects/install-on-windows/en/latest/install/install.html
#    - OR from GitHub: https://github.com/ROCm/rocm-install-on-windows/releases

# 2. Run setup script
cd G:\Docker\resilient-rap-framework
powershell -ExecutionPolicy Bypass -File setup_windows_hip.ps1

# 3. Verify GPU works
powershell -ExecutionPolicy Bypass -File verify_windows_hip.ps1

# 4. Run pipeline
python tools/cadillac_gpu_stress_test.py --iterations 100
```

## Scripts

### `setup_windows_hip.ps1` (Main Setup)
**What it does:**
- Checks for Visual Studio compiler (cl.exe)
- Verifies HIP for Windows installation
- Tests GPU detection with `hipinfo`
- Installs PyTorch for HIP (GPU-accelerated)
- Builds `fast_ingest.cpp` C++ extension
- Runs comprehensive GPU tests

**Usage:**
```powershell
cd G:\Docker\resilient-rap-framework
powershell -ExecutionPolicy Bypass -File setup_windows_hip.ps1

# Or with options:
powershell -ExecutionPolicy Bypass -File setup_windows_hip.ps1 -SkipVSCheck -SkipPyTorch
```

**Options:**
- `-SkipVSCheck` — Skip compiler check (if already installed)
- `-SkipHIPCheck` — Skip HIP check (if already installed)
- `-SkipPyTorch` — Skip PyTorch installation (if already installed)
- `-SkipBuild` — Skip extension build (if already built)
- `-TestOnly` — Only run tests, don't build

### `verify_windows_hip.ps1` (Verification)
**What it does:**
- Quick diagnostic of all components
- Tests GPU acceleration
- Verifies `fast_ingest` extension loads

**Usage:**
```powershell
powershell -ExecutionPolicy Bypass -File verify_windows_hip.ps1
```

**Output example:**
```
Checking Windows HIP Setup...

✓ Visual Studio Compiler (cl.exe)
✓ HIP Installation
✓ PyTorch GPU Detection
✓ GPU Math OK
✓ CPU Ingest
✓ GPU Normalize
✓ All checks passed!
```

### `setup_windows_hip.bat` (Batch Launcher)
**What it does:**
- Wrapper for users who prefer batch files
- Automatically bypasses PowerShell execution policy

**Usage:**
```cmd
cd G:\Docker\resilient-rap-framework
setup_windows_hip.bat
```

Or double-click the file directly.

## Step-by-Step Installation

### Prerequisites (Install Once)

#### 1. Visual Studio Build Tools
```
1. Go to https://visualstudio.microsoft.com/downloads/
2. Download "Visual Studio Build Tools 2022"
3. Run installer
4. Select "Desktop development with C++"
5. Click Install (~3 GB download)
6. Restart your computer
```

Verify:
```powershell
where cl.exe
# Expected: C:\Program Files (x86)\Microsoft Visual Studio\...
```

#### 2. HIP for Windows
```
1. Go to https://github.com/ROCm/HIP-windows/releases
2. Download latest: HIP-6.2.windows-installer.exe
3. Run installer
4. Select "Add ROCm to PATH" (important!)
5. Finish installation
6. Restart PowerShell
```

Verify:
```powershell
hipinfo
# Expected:
#   gfx1100 (your 7900 XT)
#   ...
```

### Automated Setup

Once prerequisites are installed:

```powershell
cd G:\Docker\resilient-rap-framework
powershell -ExecutionPolicy Bypass -File setup_windows_hip.ps1
```

This will:
1. ✓ Check compiler & HIP
2. ✓ Install PyTorch for HIP
3. ✓ Build `fast_ingest.cpp` extension
4. ✓ Test GPU acceleration
5. ✓ Show success or detailed errors

### Manual Verification

If setup script fails, manually verify each step:

```powershell
# Test 1: Compiler
cl.exe /?

# Test 2: HIP GPU detection
hipinfo

# Test 3: PyTorch GPU
python -c "import torch; print(torch.cuda.is_available())"

# Test 4: Extension build
cd G:\Docker\resilient-rap-framework
python setup.py build_ext --inplace
```

## Troubleshooting

### Problem: `hipinfo: command not found`

**Solution:**
```powershell
# Verify HIP installed
dir "C:\Program Files\AMD\ROCm\bin"

# Add to PATH temporarily
$env:PATH += ";C:\Program Files\AMD\ROCm\bin"
hipinfo

# Or restart PowerShell completely
```

### Problem: `torch.cuda.is_available()` returns `False`

**Cause:** Wrong PyTorch installed (CUDA instead of HIP)

**Solution:**
```powershell
# Check version
pip show torch | findstr Version
# Should contain "+rocm" or "+hip"

# If not, reinstall:
pip uninstall torch -y
pip install torch --index-url https://download.pytorch.org/whl/hip
```

### Problem: `cl.exe not found` during build

**Solution:**
```powershell
# Install Visual Studio Build Tools from
# https://visualstudio.microsoft.com/downloads/
# Select: Desktop development with C++

# Or add to PATH if already installed:
$env:PATH += ";C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\LLVM\bin"
```

### Problem: `fast_ingest.pyd` not found after build

**Solution:**
```powershell
# Check build output
cd G:\Docker\resilient-rap-framework
python setup.py build_ext --inplace 2>&1 | findstr error

# If still fails, try with explicit compiler:
python setup.py build_ext --inplace --compiler=msvc
```

### Problem: GPU test passes but `ingest_batch()` fails

**Cause:** Insufficient GPU memory or device synchronization issue

**Solution:**
```powershell
# Check GPU memory
python -c "import torch; print(torch.cuda.get_device_properties(0).total_memory / 1e9, 'GB')"

# Try smaller batch size
python -c "
import fast_ingest
s = fast_ingest.StreamingIngestor([0]*10, [100]*10, batch_size=32)  # smaller batch
"
```

## Running the Pipeline

Once setup is verified, you can run:

### Quick GPU Stress Test
```powershell
python tools/cadillac_gpu_stress_test.py --iterations 100 --batch-size 128
```

Expected output:
```
Cadillac F1 GPU Stress Test
===========================
Iteration 100/100
  Packets: 12800
  Time: 23.4s
  Rate: 546 packets/sec
  GPU: Active (device='cuda:0')
```

### Full Pipeline Demo
```powershell
python examples/demo_hitl_retraining.py
```

### Interactive TUI
```powershell
python tools/tui_replayer.py
```

## Performance Expectations

On AMD 7900 XT with Windows HIP:

| Metric                | Value      |
|----------------------|------------|
| Ingestion Rate       | 450-550 pkt/sec |
| Latency (p99)        | ~2-3 ms    |
| GPU Utilization      | 15-25%     |
| Memory (batch=128)   | ~100 MB    |

These are slightly lower than Linux ROCm (~85% parity) but still very fast.

## Next Steps

### For Development
1. Make changes to Python code in `modules/` or `tools/`
2. For C++ changes, rebuild: `python setup.py build_ext --inplace --force`
3. Re-test with `verify_windows_hip.ps1`

### For Production (Linux Deployment)
1. The same code compiles on Linux with ROCm
2. Use Docker (see [GETTING_STARTED.md](../GETTING_STARTED.md))
3. Get ~15% better performance on Linux servers

### For Dual-Boot Setup
1. Install Ubuntu 22.04 alongside Windows
2. Follow [GETTING_STARTED.md](../GETTING_STARTED.md) for Linux ROCm setup
3. Use Windows for dev, Linux for demos/production

## References

- **HIP Documentation:** https://rocmdocs.amd.com/en/docs-6.2.1/deploy/windows/
- **PyTorch HIP Builds:** https://download.pytorch.org/whl/hip
- **AMD 7900 XT Specs:** https://www.amd.com/en/products/graphics/amd-radeon-rx-7900-xt
- **Resilient RAP Docs:** See [../README.md](../README.md) and [../OPERATIONS.md](../OPERATIONS.md)

## Questions?

Check the main [README.md](../README.md) or [WINDOWS_SETUP.md](../WINDOWS_SETUP.md) for detailed explanations.
