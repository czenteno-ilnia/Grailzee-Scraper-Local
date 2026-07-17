@echo off
setlocal

cd /d "%~dp0"

set "VENV_DIR=.venv_windows"
set "PYTHON_CMD=python"
set "UPDATE_URL=https://raw.githubusercontent.com/czenteno-ilnia/Grailzee-Scraper-Local/main/update.py"
set "UPDATE_TMP=update.py.tmp"

if exist "%VENV_DIR%\Scripts\python.exe" set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"

echo ======================================
echo  Starting Grailzee Scraper for Windows
echo ======================================

if not defined GRAILZEE_SKIP_UPDATE (
    echo Buscando actualizaciones...
    curl -fsSL -o "%UPDATE_TMP%" "%UPDATE_URL%" >nul 2>&1
    if errorlevel 1 (
        "%PYTHON_CMD%" -c "import urllib.request; urllib.request.urlretrieve(r'%UPDATE_URL%', r'%UPDATE_TMP%')" >nul 2>&1
    )
    if errorlevel 1 (
        del "%UPDATE_TMP%" >nul 2>&1
        echo [AVISO] No se pudo descargar la actualizacion. Se usara el codigo local.
    ) else (
        move /y "%UPDATE_TMP%" update.py >nul
        "%PYTHON_CMD%" update.py
    )
)

if not exist "requirements.txt" (
    echo [ERROR] Falta el codigo de la app y no se pudo descargar.
    echo Revisa tu conexion a internet y vuelve a abrir.
    pause
    exit /b 1
)

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
