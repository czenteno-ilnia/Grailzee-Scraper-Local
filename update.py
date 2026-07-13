"""Auto-actualizador de Grailzee. Baja el código último del repo público y lo copia
sobre esta carpeta, respetando config, reportes, credenciales y entornos virtuales.

Lo llaman los launchers (app.sh / Windows.bat / Mac.command) al arrancar. Se puede saltar
con la variable de entorno GRAILZEE_SKIP_UPDATE=1.

Sin dependencias: solo stdlib. ponytail: misma lógica de copia que el botón in-app
(_copy_update en MainApp.py); si divergen, este archivo es la fuente para los launchers.
"""
import os
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
import shutil


def _download(url, dest):
    try:
        subprocess.run(["curl", "-fsSL", "-o", dest, url], check=True)
    except Exception:
        urllib.request.urlretrieve(url, dest)

ZIP_URL = "https://github.com/czenteno-ilnia/Grailzee-Scraper-Local/archive/refs/heads/main.zip"

SKIP_DIRS = {".git", "reportes", "logs", "local", "__pycache__",
             ".venv_windows", ".venv_unix", ".venv_mac", "env"}
SKIP_FILES = {"settings.json", ".env"}
ALLOW_EXT = {".py", ".bat", ".sh", ".command", ".txt", ".md"}


def update(dst="."):
    dst = os.path.abspath(dst)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "update.zip")
        _download(ZIP_URL, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        roots = [os.path.join(tmp, d) for d in os.listdir(tmp)
                 if os.path.isdir(os.path.join(tmp, d)) and d.lower().startswith("grailzee")]
        if not roots:
            raise RuntimeError("zip con estructura inesperada")
        src = roots[0]
        count = 0
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            rel = os.path.relpath(root, src)
            target_dir = dst if rel == "." else os.path.join(dst, rel)
            for f in files:
                if f in SKIP_FILES or os.path.splitext(f)[1].lower() not in ALLOW_EXT:
                    continue
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(os.path.join(root, f), os.path.join(target_dir, f))
                count += 1
        return count


if __name__ == "__main__":
    if os.environ.get("GRAILZEE_SKIP_UPDATE"):
        print("Update saltado (GRAILZEE_SKIP_UPDATE).")
        sys.exit(0)
    try:
        n = update()
        print(f"Actualizado: {n} archivo(s) desde GitHub.")
    except Exception as e:
        # Nunca bloquear el arranque: si no hay internet o falla, seguimos con lo local
        print(f"[AVISO] Update saltado: {e}")
        sys.exit(0)
