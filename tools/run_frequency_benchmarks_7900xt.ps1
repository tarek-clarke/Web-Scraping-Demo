# Resilient RAP Framework - 7900XT Frequency Benchmark Suite
# 1000Hz and 1MHz (Sprint/30k and Weekend/3.6M)

$ErrorActionPreference = "Stop"

$Frequencies = @(1000000, 1000)
$Profiles = @(
    @{ Name = "Sprint"; Packets = 2000 },
    @{ Name = "Weekend"; Packets = 240000 }
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   7900XT FREQUENCY SCALING BENCHMARKS (1000Hz, 1MHz)     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

foreach ($Freq in $Frequencies) {
    foreach ($RunProfile in $Profiles) {
        $FreqLabel = if ($Freq -ge 1000000) { "$($Freq/1000000)MHz" } else { "$($Freq)Hz" }
        $OutputSuffix = "_$($FreqLabel)_$($RunProfile.Name)_7900XT"
        
        Write-Host "`n>>> Running: $FreqLabel | $($RunProfile.Name) ($($RunProfile.Packets) packets)" -ForegroundColor Yellow
        
        python tools/telemetry_gpu_stress_test.py `
            --packets $($RunProfile.Packets) `
            --frequency $Freq `
            --output-suffix $OutputSuffix `
            --chaos 0.12 `
            --chaos-profile balanced
            
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Benchmark failed for $FreqLabel / $($RunProfile.Name)" -ForegroundColor Red
            exit $LASTEXITCODE
        }
    }
}

Write-Host "`nAll frequency benchmarks complete! Results in data/reports/7900XT" -ForegroundColor Green
