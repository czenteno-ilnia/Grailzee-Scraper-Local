@echo off
REM ==============================
REM 🧠 Script de inicio para Google Sheets + eBay Scraper
REM ==============================

echo ======================================
echo  Creando entorno virtual "env"
echo ======================================

REM Verificar si ya existe el entorno virtual
if not exist env (
    python -m venv env
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual / Could not create the virtual environment.
        pause
        exit /b 1
    )
    echo ✅ Entorno virtual creado.
) else (
    echo ⚙️  El entorno virtual ya existe.
)

REM Activar el entorno virtual
call env\Scripts\activate
if errorlevel 1 (
    echo [ERROR] No se pudo activar el entorno virtual / Could not activate the virtual environment.
    pause
    exit /b 1
)

python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] pip no está disponible en el entorno. Ejecutando ensurepip / pip is missing. Running ensurepip...
    python -m ensurepip --upgrade
    if errorlevel 1 (
        echo [ERROR] No se pudo inicializar pip con ensurepip / Could not bootstrap pip with ensurepip.
        pause
        exit /b 1
    )
)

echo ======================================
echo  Instalando dependencias necesarias...
echo ======================================

python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] No se pudo actualizar pip / Could not upgrade pip.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias / Could not install dependencies.
    pause
    exit /b 1
)


echo ======================================
echo  Dependencias instaladas correctamente.
echo ======================================

REM Ejecutar el programa principal
echo 🚀 Iniciando el programa MainApp.py...
python MainApp.py
if errorlevel 1 (
    echo [ERROR] No se pudo iniciar MainApp.py / Could not launch MainApp.py.
    pause
    exit /b 1
)

REM Mantener ventana abierta después de ejecución
echo.
pause
