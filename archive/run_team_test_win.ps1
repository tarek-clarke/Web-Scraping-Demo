# Team Testing — Windows Parallel Concurrency Wrapper
# Launches two parallel telemetry-gpu-stress-test runs on the same GPU

$Packets = $args[0]
if (-not $Packets) { $Packets = 2000 }
$Chaos = $args[1]
if (-not $Chaos) { $Chaos = 0.05 }

Write-Host "🏁 STARTING TEAM TEST (Windows): Two Cars | Single GPU"
Write-Host "--- Configuration ---"
Write-Host "Packets: $Packets"
Write-Host "Chaos:   $Chaos"
Write-Host "---------------------"

$env:PYTHONPATH = "."

# Launch Car 1
Write-Host "⚡ Launching Car 1 Benchmark..."
$Job1 = Start-Process python -ArgumentList "tools/telemetry_gpu_stress_test.py --packets $Packets --chaos $Chaos --output-suffix _team_car1" -PassThru -NoNewWindow

# Launch Car 2
Write-Host "⚡ Launching Car 2 Benchmark..."
$Job2 = Start-Process python -ArgumentList "tools/telemetry_gpu_stress_test.py --packets $Packets --chaos $Chaos --output-suffix _team_car2" -PassThru -NoNewWindow

Write-Host "⏳ Monitoring parallel execution (PIDs: $($Job1.Id), $($Job2.Id))..."

$Job1.WaitForExit()
Write-Host "✅ Car 1 Complete"

$Job2.WaitForExit()
Write-Host "✅ Car 2 Complete"

Write-Host "🏆 TEAM TEST COMPLETE"
