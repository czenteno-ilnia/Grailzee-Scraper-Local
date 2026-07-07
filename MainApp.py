import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import os
import json
import re
import glob
from datetime import datetime
import pandas as pd
import sv_ttk
import dedupe as dd

# === SCRAPERS ===
import scraper_ebay
import scraper_chrono24

CONFIG_FILE = "settings.json"

def load_settings():
    if not os.path.exists(CONFIG_FILE):
        default = {"report_dir": "reportes", "oxy_usage": {}}
        save_settings(default)
        return default
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
        if "oxy_usage" not in data:
            data["oxy_usage"] = {}
        return data

def save_settings(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

settings = load_settings()

class GrailzeeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Grailzee Scraper")
        self.root.geometry("1200x820")
        self.root.minsize(900, 650)
        self._scraping = False
        self._build_ui()
        self._update_latest_info()
        self._update_usage_ui()

    def _build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=16, pady=(12, 4))

        ttk.Label(top, text="⌚ Grailzee Scraper", font=("Segoe UI", 18, "bold")).pack(side="left")
        
        self.lbl_usage = ttk.Label(top, text="Oxylabs local: 0 req", font=("Segoe UI", 10))
        self.lbl_usage.pack(side="right", padx=8)

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=16, pady=4)

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=16, pady=4)

        left = ttk.Frame(body, width=460)
        left.pack(side="left", fill="both", expand=False, padx=(0, 8))
        left.pack_propagate(False)

        ttk.Label(left, text="URLs (una por línea)", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))
        self.txt_urls = scrolledtext.ScrolledText(left, width=55, height=8, font=("Consolas", 10))
        self.txt_urls.pack(fill="x", pady=(0, 8))

        save_row = ttk.Frame(left)
        save_row.pack(fill="x", pady=(0, 6))
        ttk.Label(save_row, text="Guardar en:", width=11).pack(side="left", padx=(0, 4))
        self.entry_report_name = ttk.Entry(save_row, width=28)
        self.entry_report_name.pack(side="left")
        ttk.Label(save_row, text="(vacío = fecha)", font=("Segoe UI", 8)).pack(side="left", padx=(4, 0))

        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x", pady=(0, 12))
        self.btn_scrape = ttk.Button(btn_row, text="🚀  Iniciar Scraping", command=self.start_scraper)
        self.btn_scrape.pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Limpiar", command=lambda: self.txt_urls.delete("1.0", tk.END)).pack(side="left", padx=(0, 6))

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)

        ttk.Label(left, text="Reportes", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Button(left, text="📄 Abrir último reporte", command=self._open_csv).pack(anchor="w", pady=(0, 4))

        self.lbl_csv_info = ttk.Label(left, text="", font=("Segoe UI", 9))
        self.lbl_csv_info.pack(anchor="w", pady=(2, 4))

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)

        ttk.Label(left, text="Configuración", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))
        cfg_row = ttk.Frame(left)
        cfg_row.pack(fill="x", pady=(0, 4))
        ttk.Label(cfg_row, text="Carpeta reportes:").pack(side="left", padx=(0, 4))
        self.entry_report_dir = ttk.Entry(cfg_row, width=24)
        self.entry_report_dir.pack(side="left", padx=(0, 4))
        self.entry_report_dir.insert(0, settings.get("report_dir", "reportes"))
        ttk.Button(cfg_row, text="📁", command=self._choose_folder, width=3).pack(side="left")

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)

        ttk.Label(left, text="Credenciales Oxylabs", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))
        oxy_row1 = ttk.Frame(left)
        oxy_row1.pack(fill="x", pady=(0, 4))
        ttk.Label(oxy_row1, text="Usuario:").pack(side="left", padx=(0, 4))
        self.entry_oxy_user = ttk.Entry(oxy_row1, width=25)
        self.entry_oxy_user.pack(side="left")
        self.entry_oxy_user.insert(0, settings.get("oxy_user", ""))
        self.entry_oxy_user.bind("<KeyRelease>", lambda e: self._update_usage_ui())

        oxy_row2 = ttk.Frame(left)
        oxy_row2.pack(fill="x", pady=(0, 4))
        ttk.Label(oxy_row2, text="Contraseña:").pack(side="left", padx=(0, 4))
        self.entry_oxy_pass = ttk.Entry(oxy_row2, width=25, show="*")
        self.entry_oxy_pass.pack(side="left")
        self.entry_oxy_pass.insert(0, settings.get("oxy_pass", ""))

        hook_row = ttk.Frame(left)
        hook_row.pack(fill="x", pady=(4, 0))
        ttk.Label(hook_row, text="Webhook (opcional):").pack(side="left", padx=(0, 4))
        self.entry_webhook = ttk.Entry(hook_row, width=25)
        self.entry_webhook.pack(side="left")
        self.entry_webhook.insert(0, settings.get("webhook_url", ""))

        ttk.Button(left, text="Guardar config", command=self._save_config).pack(anchor="w", pady=(8, 0))

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(right, text="Output", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))
        self.txt_log = scrolledtext.ScrolledText(right, width=75, height=36, state="disabled", font=("Consolas", 10))
        self.txt_log.pack(fill="both", expand=True)

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=16, pady=(4, 10))

        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 4))

        self.lbl_status = ttk.Label(bottom, text="Listo.", font=("Segoe UI", 9))
        self.lbl_status.pack(anchor="w")

    def log(self, text):
        self.txt_log.config(state="normal")
        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state="disabled")

    def _set_status(self, text):
        self.lbl_status.config(text=text)

    def _update_usage_ui(self):
        user = self.entry_oxy_user.get().strip()
        usage_dict = settings.get("oxy_usage", {})
        count = usage_dict.get(user, 0)
        self.lbl_usage.config(text=f"Oxylabs local: {count} req")

    def _increment_usage(self):
        user = self.entry_oxy_user.get().strip()
        if user:
            usage_dict = settings.get("oxy_usage", {})
            usage_dict[user] = usage_dict.get(user, 0) + 1
            settings["oxy_usage"] = usage_dict
            self.root.after(0, self._update_usage_ui)

    def _latest_csv(self, report_dir):
        csvs = glob.glob(os.path.join(report_dir, "*.csv"))
        return max(csvs, key=os.path.getmtime) if csvs else None

    def _update_latest_info(self):
        report_dir = settings.get("report_dir", "reportes")
        os.makedirs(report_dir, exist_ok=True)
        latest = self._latest_csv(report_dir)
        if not latest:
            self.lbl_csv_info.config(text="  Sin reportes aún")
            return
        name = os.path.basename(latest)
        try:
            df = pd.read_csv(latest)
            self.lbl_csv_info.config(text=f"  📋 {len(df)} items en {name}")
        except Exception:
            self.lbl_csv_info.config(text=f"  ⚠️ Error leyendo {name}")

    def _open_csv(self):
        report_dir = os.path.abspath(settings.get("report_dir", "reportes"))
        # Abre el CSV más reciente (por fecha de modificación); si no hay, abre la carpeta
        target = self._latest_csv(report_dir) or report_dir
        if not os.path.exists(target):
            return self.log("⚠️ No hay reportes aún")
        import subprocess
        try:
            if os.name == 'nt':
                os.startfile(target)
            else:
                subprocess.Popen(['xdg-open', target])
        except Exception:
            self.log(f"📄 {target}")

    def _get_csv_item_ids(self, csv_path):
        if not os.path.exists(csv_path):
            return set()
        try:
            df = pd.read_csv(csv_path)
            ids = set(str(s) for s in df["Stock"].dropna())
            if "URL" in df.columns:
                for url in df["URL"].dropna():
                    url_text = str(url).split("?")[0]
                    ids.add(url_text)
                    item_id = scraper_ebay.extract_item_id(url_text)
                    if item_id: ids.add(item_id)
            return ids
        except Exception:
            return set()

    def _batch_csv_path(self):
        """Un CSV por batch. Usa el nombre del campo; si está vacío, uno por fecha/hora.
        Reusar el mismo nombre acumula en ese archivo (dedup por Stock)."""
        report_dir = settings.get("report_dir", "reportes")
        name = self.entry_report_name.get().strip()
        if not name:
            name = "batch_" + datetime.now().strftime("%Y%m%d_%H%M")
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "batch"
        if not name.lower().endswith(".csv"):
            name += ".csv"
        return os.path.join(report_dir, name)

    def start_scraper(self):
        urls = [u.strip() for u in self.txt_urls.get("1.0", tk.END).strip().split("\n") if u.strip()]
        if not urls:
            return messagebox.showwarning("Advertencia", "Debes ingresar al menos una URL.")
        if self._scraping:
            return messagebox.showinfo("Info", "Ya hay un scraping en curso.")
        
        # Guardar automáticamente la configuración al iniciar
        self._save_config()
        
        threading.Thread(target=self._run_scraper, args=(urls,), daemon=True).start()

    def _run_scraper(self, urls):
        self._scraping = True
        self.log("🔵 Iniciando scraping…")
        scraper_ebay.set_credentials(self.entry_oxy_user.get().strip(), self.entry_oxy_pass.get().strip())
        scraper_ebay.set_webhook(self.entry_webhook.get().strip())
        scraper_ebay.set_logger(self.log)  # retry/fallos de Oxylabs también al log del UI

        csv_path = self._batch_csv_path()
        self.log(f"📂 Reporte de este batch: {os.path.basename(csv_path)}")
        csv_ids_csv = self._get_csv_item_ids(csv_path)
        csv_ids_sql = dd.known_ids()
        csv_ids = csv_ids_csv | csv_ids_sql
        if csv_ids: self.log(f"📋 {len(csv_ids)} items ya en CSV → se omitirán")

        resultados = []

        def procesar(url, idx, total, etapa=""):
            """Scrapea una URL, acumula en resultados. Devuelve True si trajo/encontró datos."""
            self.log(f"\n🔍 {etapa}[{idx}/{total}] {url}")
            try:
                df = self._dispatch(url, existing_ids=csv_ids)
                if df is not None and not df.empty:
                    if csv_ids and "Stock" in df.columns:
                        before = len(df)
                        df = df[~df["Stock"].astype(str).isin(csv_ids)]
                        if before > len(df):
                            self.log(f"   ⏭️ {before - len(df)} ya en CSV, omitidos")
                    if not df.empty:
                        resultados.append(df)
                        self.log(f"   ✔ {len(df)} fila(s) nuevas")
                    else:
                        self.log("   ℹ️ Todo ya está en el CSV")
                    return True
                self.log("   ⚠️ Sin datos")
                return False
            except Exception as e:
                self.log(f"   ❌ Error: {e}")
                return False

        self._set_status(f"Scrapeando {len(urls)} URL(s)…")
        self.progress["value"] = 0
        self.progress["maximum"] = len(urls)
        fallidos = []
        for i, url in enumerate(urls, 1):
            if not procesar(url, i, len(urls)):
                fallidos.append(url)
            self.progress["value"] = i

        # Cola final: reintentar una vez los que no trajeron datos
        if fallidos:
            self.log(f"\n🔁 Reintentando {len(fallidos)} URL(s) sin datos…")
            pendientes, fallidos = fallidos, []
            self.progress["value"] = 0
            self.progress["maximum"] = len(pendientes)
            for i, url in enumerate(pendientes, 1):
                if not procesar(url, i, len(pendientes), etapa="🔁 "):
                    fallidos.append(url)
                self.progress["value"] = i

        nuevos = 0
        if resultados:
            df_new = pd.concat(resultados, ignore_index=True)
            df_new.dropna(how="all", inplace=True)
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            if os.path.exists(csv_path):
                df_existing = pd.read_csv(csv_path)
                existing_stocks = set(str(s) for s in df_existing["Stock"].dropna())
                df_new = df_new[~df_new["Stock"].astype(str).isin(existing_stocks)]
                nuevos = len(df_new)
                if not df_new.empty:
                    pd.concat([df_existing, df_new], ignore_index=True).to_csv(csv_path, index=False)
                    self.log(f"\n✅ +{nuevos} nuevos → {os.path.basename(csv_path)}")
                else:
                    self.log(f"\nℹ️ Sin items nuevos")
            else:
                nuevos = len(df_new)
                df_new.to_csv(csv_path, index=False)
                self.log(f"\n✅ {nuevos} items → {os.path.basename(csv_path)}")
            self._update_latest_info()
        else:
            self.log("\n⚠️ No se obtuvieron resultados nuevos.")

        if fallidos:
            self.log(f"\n⚠️ {len(fallidos)} URL(s) sin datos tras reintentar:")
            for u in fallidos:
                self.log(f"   • {u}")

        # Resumen al webhook (visibilidad remota); no-op si no hay webhook configurado
        resumen = (f"📊 Batch '{os.path.basename(csv_path)}': {nuevos} nuevos, "
                   f"{len(fallidos)} sin datos de {len(urls)} URL(s).")
        if fallidos:
            resumen += "\nSin datos:\n" + "\n".join(fallidos)
        scraper_ebay.post_webhook(resumen)

        self._set_status("Listo.")
        self._scraping = False

    def _dispatch(self, url, existing_ids=None):
        low = url.lower()
        if "ebay" in low: return scraper_ebay.scrape_url(url, increment_usage_callback=self._increment_usage, existing_ids=existing_ids)
        if "chrono24" in low: return scraper_chrono24.scrape_multiple([url], existing_ids=existing_ids, progress_callback=self.log)
        self.log("   ⚠️ Sitio no reconocido")
        return None

    def _choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_report_dir.delete(0, tk.END)
            self.entry_report_dir.insert(0, folder)

    def _save_config(self):
        settings["report_dir"] = self.entry_report_dir.get()
        settings["oxy_user"] = self.entry_oxy_user.get()
        settings["oxy_pass"] = self.entry_oxy_pass.get()
        settings["webhook_url"] = self.entry_webhook.get().strip()
        save_settings(settings)
        self._update_latest_info()
        self._update_usage_ui()

if __name__ == "__main__":
    root = tk.Tk()
    sv_ttk.set_theme("dark")
    app = GrailzeeApp(root)
    root.mainloop()
