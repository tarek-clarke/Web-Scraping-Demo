@echo off
rem ============================================================================
rem IEEE T-DKE Resilient Semantic Reconciliation under Drift Pipeline Runner (Windows)
rem ============================================================================

setlocal enabledelayedexpansion

echo ================================================================================
echo  ^|^| STARTING PIPELINE SYNC ^& RUN (IEEE T-DKE PRIMARY PATH)
echo ================================================================================

rem 1. Pull latest code from remote
echo [*] Syncing workspace with origin/main...
where git >nul 2>nul
if %ERRORLEVEL% equ 0 (
    git pull origin main
) else (
    echo [!] Warning: git command not found; skipping repository sync.
)

rem 2. Check or generate the static chaos dataset
set DATASET_PATH=chaos_generator\datasets\chaos_dataset.json
if not exist "%DATASET_PATH%" (
    echo [!] Warning: Static chaos dataset not found at %DATASET_PATH%.
    echo [*] Procedurally generating chaos dataset...
    python chaos_generator\generate_chaos_dataset.py ^
      --output-dir chaos_generator\datasets ^
      --runs-per-config 5 ^
      --strategies json schema
)

rem 3. Run semantic benchmark
echo [*] Executing scientific semantic translation benchmark...
python semantic_benchmark\run_semantic_benchmark.py ^
  --dataset-path "%DATASET_PATH%" ^
  --require-local-models True ^
  --strict-mode ^
  --verbose

rem 4. Auto-update README tables with latest findings
echo [*] Formatting experimental outcomes and updating tables...
python scripts\update_readme_tables.py

echo ================================================================================
echo  [x] PIPELINE SYNC, BENCHMARK EXECUTION, ^& README UPDATE COMPLETE!
echo ================================================================================
