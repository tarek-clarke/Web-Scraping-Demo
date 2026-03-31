$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "."
$env:RAP_OUTPUT_SUFFIX = "12600K"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

New-Item -ItemType Directory -Force -Path "data/reports/12600K" | Out-Null

$python = "python"

# 1. Smoke test
Write-Host "Running Smoke test..."
& $python tools/telemetry_gpu_stress_test.py --packets 20 --output-suffix _smoke | Tee-Object -FilePath "data/reports/12600K/run_log_smoke_12600K.txt"

# 2. Sprint
Write-Host "Running Sprint test..."
& $python tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.05 --output-suffix _sprint_12600K | Tee-Object -FilePath "data/reports/12600K/run_log_sprint_12600K.txt"

# 3. Weekend
Write-Host "Running Weekend test..."
& $python tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.05 --output-suffix _weekend_12600K | Tee-Object -FilePath "data/reports/12600K/run_log_weekend_12600K.txt"

# 4. Repair-focus sprint realistic (0.005)
Write-Host "Running Repair-focus Sprint realistic..."
& $python tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.005 --chaos-profile repair_focus --enable-kafka --kafka-servers localhost:9092 --kafka-topic-repairable dlq-repairable-sprint-rf005 --kafka-topic-repaired dlq-repaired-sprint-rf005 --kafka-topic-non-repairable dlq-non-repairable-sprint-rf005 --output-suffix _sprint_repairfocusrealistic_kafka_12600K | Tee-Object -FilePath "data/reports/12600K/run_log_sprint_repairfocusrealistic_kafka_12600K.txt"

# 5. Repair-focus weekend realistic (0.005)
Write-Host "Running Repair-focus Weekend realistic..."
& $python tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.005 --chaos-profile repair_focus --enable-kafka --kafka-servers localhost:9092 --kafka-topic-repairable dlq-repairable-weekend-rf005 --kafka-topic-repaired dlq-repaired-weekend-rf005 --kafka-topic-non-repairable dlq-non-repairable-weekend-rf005 --output-suffix _weekend_repairfocusrealistic_kafka_12600K | Tee-Object -FilePath "data/reports/12600K/run_log_weekend_repairfocusrealistic_kafka_12600K.txt"

# 6. Repair-focus sprint ultralow (0.001)
Write-Host "Running Repair-focus Sprint ultralow..."
& $python tools/telemetry_gpu_stress_test.py --packets 2000 --chaos 0.001 --chaos-profile repair_focus --enable-kafka --kafka-servers localhost:9092 --kafka-topic-repairable dlq-repairable-sprint-rf001 --kafka-topic-repaired dlq-repaired-sprint-rf001 --kafka-topic-non-repairable dlq-non-repairable-sprint-rf001 --output-suffix _sprint_repairfocusultralow_kafka_12600K | Tee-Object -FilePath "data/reports/12600K/run_log_sprint_repairfocusultralow_kafka_12600K.txt"

# 7. Repair-focus weekend ultralow (0.001)
Write-Host "Running Repair-focus Weekend ultralow..."
& $python tools/telemetry_gpu_stress_test.py --packets 240000 --chaos 0.001 --chaos-profile repair_focus --enable-kafka --kafka-servers localhost:9092 --kafka-topic-repairable dlq-repairable-weekend-rf001 --kafka-topic-repaired dlq-repaired-weekend-rf001 --kafka-topic-non-repairable dlq-non-repairable-weekend-rf001 --output-suffix _weekend_repairfocusultralow_kafka_12600K | Tee-Object -FilePath "data/reports/12600K/run_log_weekend_repairfocusultralow_kafka_12600K.txt"

# 8. Engine Temp specific
Write-Host "Running Engine Temp CPU test..."
& $python tools/stress_test_engine_temp.py

# 9. CPU specific default sprint
Write-Host "Running basic telemetry parameter stress test sprint..."
& $python tools/telemetry_stress_test.py --packets 2000 --chaos 0.05

Write-Host "All tests completed!"
