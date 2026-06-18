@echo off
setlocal enabledelayedexpansion
REM TakeoverBench - Windows startup script
REM Make sure CarlaUE4.exe is running BEFORE executing this.

echo ============================================
echo   TakeoverBench Server (Windows)
echo   Make sure CARLA is running before connecting
echo ============================================

REM ── Detect Python: prefer py launcher with 3.12 ──
set "PY_CMD=python"
py --list >nul 2>nul
if !errorlevel! equ 0 (
    py -3.12 --version >nul 2>nul
    if !errorlevel! equ 0 (
        echo [PYTHON] Using py launcher: Python 3.12
        set "PY_CMD=py -3.12"
    ) else (
        echo [PYTHON] Python 3.12 not found via py launcher.
        echo [PYTHON] CARLA 0.9.16 requires Python 3.7-3.12.
        echo [PYTHON] Install Python 3.12 from https://www.python.org/downloads/
        echo [PYTHON] Falling back to default python...
    )
)

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo [STARTUP] Activating venv...
    call venv\Scripts\activate.bat
) else (
    echo [STARTUP] No venv found - using system Python
)

REM Install Python dependencies
echo [STARTUP] Installing Python dependencies...
%PY_CMD% -m pip install -e . --quiet

REM Install CARLA Python API (delegated to Python to avoid batch .env parsing)
echo [STARTUP] Checking for CARLA Python API...
%PY_CMD% -c "import carla" 2>nul
if errorlevel 1 (
    echo [CARLA] CARLA Python module not found.
    %PY_CMD% scripts\install_carla_api.py
    if errorlevel 1 (
        pause
        exit /b 1
    )
) else (
    echo [CARLA] CARLA Python module already available.
)

echo [STARTUP] Starting Flask server...
%PY_CMD% server.py

pause
