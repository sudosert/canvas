@echo off
REM SD Image Viewer Launcher Script
REM This script activates the virtual environment and launches the application

setlocal EnableDelayedExpansion

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo SD Image Viewer Launcher
echo ========================

REM Check if virtual environment exists
if not exist ".venv" (
    echo Virtual environment not found. Creating one...
    
    REM Check if python is available
    python --version >nul 2>&1
    if errorlevel 1 (
        echo Error: Python is not installed or not in PATH
        pause
        exit /b 1
    )
    
    REM Create virtual environment
    python -m venv .venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created.
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if requirements are installed
if not exist ".requirements_installed" (
    goto :install_requirements
)

REM Check if requirements.txt is newer than the marker file
for %%F in (requirements.txt) do set "REQ_TIME=%%~tF"
for %%F in (.requirements_installed) do set "INST_TIME=%%~tF"

REM Simple check - if marker exists, we assume requirements are installed
REM For a more robust check, we'd need to compare timestamps properly
if "%REQ_TIME%" gtr "%INST_TIME%" (
    goto :install_requirements
)

goto :launch

:install_requirements
echo Installing/updating requirements...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install requirements
    pause
    exit /b 1
)
type nul > .requirements_installed
echo Requirements installed.

:launch
echo Launching SD Image Viewer...
python src/main.py %*

REM Deactivate virtual environment
call .venv\Scripts\deactivate.bat

endlocal
