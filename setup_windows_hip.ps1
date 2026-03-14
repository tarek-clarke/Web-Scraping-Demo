# Windows HIP Setup Automation Script
# Installs PyTorch for HIP, builds fast_ingest.cpp, and verifies GPU
# Usage: powershell -ExecutionPolicy Bypass -File setup_windows_hip.ps1

param(
    [switch]$SkipVSCheck = $false,
    [switch]$SkipHIPCheck = $false,
    [switch]$SkipPyTorch = $false,
    [switch]$SkipBuild = $false,
    [switch]$TestOnly = $false
)

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $color = @{
        "INFO" = "Cyan"
        "SUCCESS" = "Green"
        "ERROR" = "Red"
        "WARNING" = "Yellow"
    }[$Status]
    Write-Host "[$Status] $Message" -ForegroundColor $color
}

function Test-CompilerExists {
    Write-Status "Checking for C++ compiler (cl.exe)..." "INFO"
    
    $cl = Get-Command cl.exe -ErrorAction SilentlyContinue
    if ($cl) {
        Write-Status "Found compiler: $($cl.Path)" "SUCCESS"
        return $true
    }
    
    Write-Status "C++ compiler (cl.exe) not found!" "ERROR"
    Write-Status "Install Visual Studio Build Tools from:" "ERROR"
    Write-Status "  https://visualstudio.microsoft.com/downloads/" "ERROR"
    Write-Status "Select: 'Desktop development with C++'" "ERROR"
    return $false
}

function Test-HIPInstalled {
    Write-Status "Checking for HIP installation..." "INFO"
    
    # Check ROCm 7.1 (latest)
    $hipPath = "C:\Program Files\AMD\ROCm\7.1"
    if ((Test-Path $hipPath) -and (Test-Path "$hipPath\bin\hipInfo.exe")) {
        Write-Status "Found HIP at: $hipPath" "SUCCESS"
        $env:PATH += ";$hipPath\bin;$hipPath\lib"
        return $true
    }
    
    # Check ROCm 6.4
    $hipPath = "C:\Program Files\AMD\ROCm\6.4"
    if ((Test-Path $hipPath) -and (Test-Path "$hipPath\bin\hipInfo.exe")) {
        Write-Status "Found HIP at: $hipPath" "SUCCESS"
        $env:PATH += ";$hipPath\bin;$hipPath\lib"
        return $true
    }
    
    Write-Status "HIP SDK for Windows not found!" "ERROR"
    Write-Status "Download from:" "ERROR"
    Write-Status "  https://rocm.docs.amd.com/projects/install-on-windows/en/latest/install/install.html" "ERROR"
    Write-Status "OR from GitHub:" "ERROR"
    Write-Status "  https://github.com/ROCm/rocm-install-on-windows/releases" "ERROR"
    return $false
}

function Test-GPUDetection {
    Write-Status "Testing GPU detection with hipInfo..." "INFO"
    
    try {
        $hipinfo = &"C:\Program Files\AMD\ROCm\7.1\bin\hipInfo.exe" 2>&1
        if ($hipinfo -match "gfx1100|AMD Radeon RX 7900") {
            Write-Status "[OK] GPU detected: AMD RDNA3 (7900 XT)" "SUCCESS"
            $hipinfo | Where-Object { $_ -match "Name:|memInfo" } | ForEach-Object { Write-Status "  $_" }
            return $true
        } else {
            Write-Status "GPU detection unclear. Output:" "WARNING"
            $hipinfo | Select-Object -First 20 | ForEach-Object { Write-Status "  $_" }
            return $true  # Don't fail, user might have different GPU
        }
    } catch {
        Write-Status "hipInfo failed: $_" "ERROR"
        return $false
    }
}

function Install-PyTorchHIP {
    Write-Status "Upgrading pip, setuptools..." "INFO"
    pip install --upgrade pip setuptools wheel
    
    Write-Status "Uninstalling old PyTorch versions..." "INFO"
    $ErrorActionPreference = "Continue"
    pip uninstall torch torchvision torchaudio -y 2>&1 | out-null
    $ErrorActionPreference = "Stop"
    
    Write-Status "Installing PyTorch for HIP (Windows)..." "INFO"
    Write-Status "This may take 2-3 minutes..." "INFO"
    
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/hip
    
    if ($LASTEXITCODE -ne 0) {
        Write-Status "PyTorch installation failed!" "ERROR"
        return $false
    }
    
    Write-Status "PyTorch for HIP installed successfully" "SUCCESS"
    return $true
}

function Test-PyTorchGPU {
    Write-Status "Testing PyTorch GPU support..." "INFO"
    
    $testCode = @'
import sys
import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    sys.exit(0)
else:
    print("ERROR: GPU not detected!")
    sys.exit(1)
'@
    
    python -c $testCode
    
    if ($LASTEXITCODE -eq 0) {
        Write-Status "PyTorch GPU support verified" "SUCCESS"
        return $true
    } else {
        Write-Status "PyTorch GPU support test failed" "ERROR"
        return $false
    }
}

function Build-FastIngest {
    Write-Status "Building fast_ingest.cpp extension..." "INFO"
    
    if (!(Test-Path "setup.py")) {
        Write-Status "setup.py not found! Make sure you're in the repo root" "ERROR"
        return $false
    }
    
    Write-Status "Cleaning old build artifacts..." "INFO"
    rm -r build, dist, *.egg-info -Force -ErrorAction SilentlyContinue | out-null
    
    Write-Status "Running: python setup.py build_ext --inplace" "INFO"
    python setup.py build_ext --inplace
    
    if ($LASTEXITCODE -ne 0) {
        Write-Status "Build failed!" "ERROR"
        return $false
    }
    
    # Check if .pyd was created
    $pyd = Get-ChildItem "fast_ingest*.pyd" -ErrorAction SilentlyContinue
    if ($pyd) {
        Write-Status "[OK] Extension built: $($pyd.Name)" "SUCCESS"
        return $true
    } else {
        Write-Status "Extension file not found after build!" "ERROR"
        return $false
    }
}

function Test-FastIngest {
    Write-Status "Testing fast_ingest GPU functions..." "INFO"
    
    $testCode = @'
import sys
import torch
import fast_ingest

try:
    # Test 1: CPU ingest
    result = fast_ingest.ingest([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    print(f"[OK] CPU ingest: shape={result.shape}, device={result.device}")
    
    # Test 2: GPU normalize
    lo = [80.0, 4000.0, 0.0, 100.0, 70.0, 150.0, 19.0, 0.0, 55.0, -6.0]
    hi = [360.0, 15500.0, 100.0, 1100.0, 130.0, 2800.0, 28.0, 65535.0, 200.0, 6.0]
    packet = [200.0, 8000.0, 50.0, 600.0, 100.0, 1500.0, 23.0, 32768.0, 100.0, 3.0]
    
    result = fast_ingest.normalize(packet, lo, hi)
    on_gpu = 'cuda' in str(result.device)
    print(f"[OK] GPU normalize: device={result.device}, on_gpu={on_gpu}")
    
    # Test 3: Batch
    batch = [packet] * 10
    result = fast_ingest.ingest_batch(batch, lo, hi)
    print(f"[OK] Batch GPU: shape={result.shape}, device={result.device}")
    
    if on_gpu:
        print("SUCCESS: All tests passed, GPU acceleration active!")
        sys.exit(0)
    else:
        print("WARNING: Tests passed but not using GPU (may be running on CPU)")
        sys.exit(1)
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'@
    
    python -c $testCode
    return ($LASTEXITCODE -eq 0)
}

function Main {
    Write-Host ""
    Write-Status "======================================" "INFO"
    Write-Status "Windows HIP Setup - Resilient RAP" "INFO"
    Write-Status "AMD 7900 XT GPU Acceleration" "INFO"
    Write-Status "======================================" "INFO"
    Write-Host ""
    
    Write-Status "System: Windows" "INFO"
    Write-Status "Target GPU: AMD Radeon RX 7900 XT (gfx1100)" "INFO"
    Write-Host ""
    
    # Step 1: Check prerequisites
    if (-not $SkipVSCheck) {
        if (-not (Test-CompilerExists)) {
            Write-Status "Install Visual Studio Build Tools and rerun this script." "ERROR"
            exit 1
        }
        Write-Host ""
    }
    
    if (-not $SkipHIPCheck) {
        if (-not (Test-HIPInstalled)) {
            Write-Status "Install HIP for Windows and rerun this script." "ERROR"
            exit 1
        }
        Write-Host ""
        
        if (-not (Test-GPUDetection)) {
            Write-Status "GPU detection failed. Check installation." "WARNING"
        }
        Write-Host ""
    }
    
    # Step 2: Install PyTorch
    if (-not $SkipPyTorch) {
        if (-not (Install-PyTorchHIP)) {
            exit 1
        }
        Write-Host ""
        
        if (-not (Test-PyTorchGPU)) {
            exit 1
        }
        Write-Host ""
    }
    
    # Step 3: Build extension
    if (-not $SkipBuild) {
        if (-not (Build-FastIngest)) {
            exit 1
        }
        Write-Host ""
    }
    
    # Step 4: Test everything
    if (-not $TestOnly) {
        if (Test-FastIngest) {
            Write-Host ""
            Write-Status "======================================" "SUCCESS"
            Write-Status "[OK] Setup complete! GPU is ready." "SUCCESS"
            Write-Status "======================================" "SUCCESS"
            Write-Host ""
            Write-Status "Next: Run the pipeline:" "INFO"
            Write-Status "  python examples/demo_hitl_retraining.py" "INFO"
            Write-Status "  or" "INFO"
            Write-Status "  python tools/telemetry_gpu_stress_test.py" "INFO"
            Write-Host ""
            exit 0
        } else {
            Write-Status "Some tests failed. Check output above." "ERROR"
            exit 1
        }
    } else {
        Write-Status "Test mode complete." "INFO"
    }
}

if ($?) {
    Main
} else {
    Write-Status "Script execution failed." "ERROR"
    exit 1
}
