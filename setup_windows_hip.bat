@echo off
REM Windows HIP Setup Launcher
REM If PowerShell execution policy blocks the script, this batch file bypasses it

setlocal enabledelayedexpansion

REM Check if PowerShell is available
where powershell >nul 2>&1
if errorlevel 1 (
    echo ERROR: PowerShell not found. Please install PowerShell or run setup_windows_hip.ps1 manually.
    pause
    exit /b 1
)

REM Run the setup script with execution policy bypass
echo Launching Windows HIP Setup...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "setup_windows_hip.ps1" %*

if errorlevel 1 (
    echo.
    echo Setup failed. See output above for details.
    pause
    exit /b 1
)

echo.
echo Setup complete!
pause
