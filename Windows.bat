@echo off
setlocal

cd /d "%~dp0"

set "VENV_DIR=.venv_windows"
set "PYTHON_CMD=python"

echo ======================================
echo  Starting Grailzee Scraper for Windows
echo ======================================

if not exist "%VENV_DIR%" (
    echo Creating virtual environment "%VENV_DIR%"...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate the virtual environment.
    pause
    exit /b 1
)

python -m ensurepip --upgrade >nul 2>&1

echo Installing dependencies...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Could not upgrade pip.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Could not install dependencies.
    pause
    exit /b 1
)

echo Launching MainApp.py...
python MainApp.py
if errorlevel 1 (
    echo [ERROR] MainApp.py exited with an error.
    pause
    exit /b 1
)

pause
