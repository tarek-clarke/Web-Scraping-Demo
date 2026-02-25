# Verify Windows HIP Setup
# Quick diagnostic script to check if GPU acceleration is working

param(
    [switch]$Verbose = $false
)

function Test-Component {
    param([string]$Name, [scriptblock]$Test)
    
    try {
        $result = & $Test
        if ($result) {
            Write-Host "✓ $Name" -ForegroundColor Green
            return $true
        } else {
            Write-Host "✗ $Name" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "✗ $Name (Error: $_)" -ForegroundColor Red
        return $false
    }
}

Write-Host ""
Write-Host "Checking Windows HIP Setup..." -ForegroundColor Cyan
Write-Host ""

$checks = @(
    @{
        Name = "Visual Studio Compiler (cl.exe)"
        Test = { (Get-Command cl.exe -ErrorAction SilentlyContinue) -ne $null }
    },
    @{
        Name = "HIP Installation"
        Test = { 
            (Test-Path "C:\Program Files\AMD\ROCm\bin\hipinfo.exe") -or `
            (Test-Path "C:\Program Files\AMD\Rocm\bin\hipinfo.exe")
        }
    }
)

$allPassed = $true
foreach ($check in $checks) {
    if (-not (Test-Component $check.Name $check.Test)) {
        $allPassed = $false
    }
}

Write-Host ""
Write-Host "PyTorch & GPU Detection" -ForegroundColor Cyan
Write-Host ""

$pytorchTest = @'
import torch
import sys

v = torch.version.__version__ if hasattr(torch, 'version') else str(torch.__version__)
print(f"Version: {v}")
print(f"GPU Available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"Device: {torch.cuda.get_device_name(0)}")
    mem = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"Memory: {mem:.2f} GB")
    
    # Test GPU operation
    t = torch.ones(1000, 1000).cuda()
    result = (t @ t).sum()
    print(f"GPU Math: OK (sum={result.item():.0f})")
'@

python -c $pytorchTest

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ PyTorch test failed" -ForegroundColor Red
    $allPassed = $false
} else {
    Write-Host "✓ PyTorch GPU Detection" -ForegroundColor Green
}

Write-Host ""
Write-Host "fast_ingest Extension" -ForegroundColor Cyan
Write-Host ""

$extensionTest = @'
try:
    import fast_ingest
    import torch
    
    # Test CPU path
    result = fast_ingest.ingest([1.0]*10)
    print(f"✓ CPU Ingest: {result.shape} on {result.device}")
    
    # Test GPU path
    lo = [0.0]*10
    hi = [100.0]*10
    packet = [50.0]*10
    result = fast_ingest.normalize(packet, lo, hi)
    
    on_gpu = 'cuda' in str(result.device)
    print(f"✓ GPU Normalize: {result.shape} on {result.device}")
    
    if not on_gpu:
        print("⚠ Warning: Not using GPU (CPU fallback active)")
    
except ImportError as e:
    print(f"✗ fast_ingest not found: {e}")
    print("  Run: python setup.py build_ext --inplace")
except Exception as e:
    print(f"✗ Error: {e}")
'@

python -c $extensionTest

if ($LASTEXITCODE -ne 0) {
    $allPassed = $false
}

Write-Host ""
if ($allPassed) {
    Write-Host "✓ All checks passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Ready to run:" -ForegroundColor Cyan
    Write-Host "  python tools/cadillac_gpu_stress_test.py" -ForegroundColor Gray
    Write-Host "  python examples/demo_hitl_retraining.py" -ForegroundColor Gray
} else {
    Write-Host "✗ Some checks failed. See output above." -ForegroundColor Red
}

Write-Host ""
