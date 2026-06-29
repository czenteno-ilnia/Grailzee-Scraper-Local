#!/bin/bash
set -e

cd "$(dirname "$0")"

VENV_DIR=".venv_unix"

echo "======================================"
echo " Starting Grailzee Scraper"
echo "======================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 is not installed. Install Python 3 first."
    exit 1
fi

if [ -z "$GRAILZEE_SKIP_UPDATE" ]; then
    echo "Buscando actualizaciones..."
    if python3 -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/czenteno-ilnia/Grailzee-Scraper-Local/main/update.py','update.py')" 2>/dev/null; then
        python3 update.py
    else
        echo "[AVISO] No se pudo actualizar (sin internet o repo no disponible)."
    fi
fi

if [ ! -f "requirements.txt" ] || [ ! -f "MainApp.py" ]; then
    echo "[ERROR] Falta el codigo de la app y no se pudo descargar."
    echo "Revisa tu conexion a internet y volve a abrir."
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

python -m ensurepip --upgrade >/dev/null 2>&1 || true

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Launching MainApp.py..."
python MainApp.py
