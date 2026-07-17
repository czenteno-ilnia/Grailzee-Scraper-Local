import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import os
import json
import re
import glob
from datetime import datetime
from urllib.parse import urlparse
import pandas as pd
import sv_ttk
import dedupe as dd

# === SCRAPERS ===
import scraper_ebay
import scraper_chrono24

CONFIG_FILE = "settings.json"
CODE_VERSION = datetime.fromtimestamp(os.path.getmtime(__file__)).strftime("%Y-%m-%d %H:%M")
SELLER_PLACEHOLDER = "Seleccionar seller…"

# temp oxy workaround
OXY_USER = "Compress5647_c5Es1"
OXY_PASS = "YVpBM7f5i++++"

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
FAILED_NOTE = "No se pudo extraer. Comprobar manualmente"


def is_valid_url(value):
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def known_single_item_key(url, existing_ids):
    """Return the known ID for a direct item URL; seller/search URLs return None."""
    clean_url = url.split("?")[0]
    ebay_item_id = scraper_ebay.extract_item_id(url)
    if ebay_item_id:
        return ebay_item_id if ebay_item_id in existing_ids else None
    if "chrono24" in url.lower() and "--id" in clean_url and clean_url.endswith(".htm"):
        return clean_url if clean_url in existing_ids else None
    return None


def localize_first_seen(df):
    """Convert Turso UTC timestamps for human-facing CSV exports."""
    if "first_seen" not in df.columns:
        return df

    def localize(value):
        if pd.isna(value) or not str(value).strip():
            return value
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError):
            return value
        if timestamp.tzinfo is None:  # Legacy rows were already written in Mexico local time.
            timestamp = timestamp.tz_localize("America/Mexico_City")
        else:
            timestamp = timestamp.tz_convert("America/Mexico_City")
        return timestamp.strftime("%Y-%m-%d %H:%M:%S %z")

    df = df.copy()
    df["first_seen"] = df["first_seen"].map(localize)
    return df

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
        threading.Thread(target=self._load_sellers, daemon=True).start()

    def _build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=16, pady=(12, 4))

        ttk.Label(top, text="⌚ Grailzee Scraper", font=("Segoe UI", 18, "bold")).pack(side="left")
        
        self.lbl_usage = ttk.Label(top, text="Oxylabs local: 0 req", font=("Segoe UI", 10))
        self.lbl_usage.pack(side="right", padx=8)
        ttk.Label(top, text=f"Código: {CODE_VERSION}", font=("Segoe UI", 9)).pack(side="right", padx=8)

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

        ttk.Label(left, text="Histórico", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))
        hist_row = ttk.Frame(left)
        hist_row.pack(fill="x", pady=(0, 4))
        self.cmb_seller = ttk.Combobox(hist_row, width=22, state="readonly")
        self.cmb_seller.set(SELLER_PLACEHOLDER)
        self.cmb_seller.pack(side="left", padx=(0, 6))
        self.btn_hist = ttk.Button(hist_row, text="📥 Seller", command=self.start_historico)
        self.btn_hist.pack(side="left", padx=(0, 6))
        self.btn_hist_all = ttk.Button(hist_row, text="📦 Todo", command=self.start_historico_all)
        self.btn_hist_all.pack(side="left")

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)

        ttk.Label(left, text="Reportes", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))
        rep_row = ttk.Frame(left)
        rep_row.pack(fill="x", pady=(0, 4))
        ttk.Button(rep_row, text="📄 Abrir último reporte", command=self._open_csv).pack(side="left", padx=(0, 6))
        ttk.Button(rep_row, text="📂 Abrir carpeta", command=self._open_folder).pack(side="left")

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
        self.entry_oxy_user.insert(0, OXY_USER)
        self.entry_oxy_user.bind("<KeyRelease>", lambda e: self._update_usage_ui())

        oxy_row2 = ttk.Frame(left)
        oxy_row2.pack(fill="x", pady=(0, 4))
        ttk.Label(oxy_row2, text="Contraseña:").pack(side="left", padx=(0, 4))
        self.entry_oxy_pass = ttk.Entry(oxy_row2, width=25, show="*")
        self.entry_oxy_pass.pack(side="left")
        self.entry_oxy_pass.insert(0, OXY_PASS)

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
        # Tkinter is not thread-safe; after() queues on the UI thread,
        # so workers can call log() directly.
        def _append():
            self.txt_log.config(state="normal")
            self.txt_log.insert(tk.END, text + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.config(state="disabled")
        self.root.after(0, _append)

    def _set_status(self, text):
        self.root.after(0, lambda: self.lbl_status.config(text=text))

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

    def _open_path(self, target):
        import subprocess
        try:
            if os.name == 'nt':
                os.startfile(target)
            else:
                subprocess.Popen(['xdg-open', target])
        except Exception:
            self.log(f"📄 {target}")

    def _open_csv(self):
        report_dir = os.path.abspath(settings.get("report_dir", "reportes"))
        # Opens the most recent CSV (by mtime); if none, opens the folder
        target = self._latest_csv(report_dir) or report_dir
        if not os.path.exists(target):
            return self.log("⚠️ No hay reportes aún")
        self._open_path(target)

    def _open_folder(self):
        report_dir = os.path.abspath(settings.get("report_dir", "reportes"))
        os.makedirs(report_dir, exist_ok=True)
        self._open_path(report_dir)

    def _get_csv_item_ids(self, csv_path):
        if not os.path.exists(csv_path):
            return set()
        try:
            df = pd.read_csv(csv_path)
            if "Make" in df.columns:
                df = df[df["Make"] != FAILED_NOTE]
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

    def _load_sellers(self):
        try:
            sellers = sorted(dd.distinct_sellers(), key=str.lower)
            self.root.after(0, lambda: self.cmb_seller.config(values=sellers))
        except Exception as e:
            self.log(f"⚠️ No se pudo cargar la lista de sellers: {e}")

    def start_historico(self):
        seller = self.cmb_seller.get().strip()
        if not seller or seller == SELLER_PLACEHOLDER:
            return messagebox.showwarning("Advertencia", "Elige un seller.")
        self._start_historico_worker(seller)

    def start_historico_all(self):
        self._start_historico_worker(None)

    def _start_historico_worker(self, seller):
        self.btn_hist.config(state="disabled")
        self.btn_hist_all.config(state="disabled")
        threading.Thread(target=self._run_historico, args=(seller,), daemon=True).start()

    def _run_historico(self, seller):
        try:
            label = f"'{seller}'" if seller else "todos los sellers"
            self.log(f"\n📥 Pulleando histórico de {label}…")
            df = dd.fetch_by_seller(seller) if seller else dd.fetch_all()
            if df.empty:
                self.log(f"ℹ️ Sin resultados para {label}")
                return
            report_dir = settings.get("report_dir", "reportes")
            os.makedirs(report_dir, exist_ok=True)
            safe = re.sub(r"[^A-Za-z0-9_-]+", "_", seller).strip("_") if seller else "completo"
            csv_path = os.path.join(report_dir, f"historico_{safe or 'seller'}_{datetime.now().strftime('%Y%m%d')}.csv")
            df = localize_first_seen(df)
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            self.log(f"✅ {len(df)} fila(s) → {os.path.basename(csv_path)}")
            self._set_status(f"✅ Histórico listo: {len(df)} filas → {os.path.basename(csv_path)}")
            self.root.after(0, self._update_latest_info)
        except Exception as e:
            self.log(f"❌ Error: {e}")
        finally:
            def _enable():
                self.btn_hist.config(state="normal")
                self.btn_hist_all.config(state="normal")
            self.root.after(0, _enable)

    def start_scraper(self):
        entries = [u.strip() for u in self.txt_urls.get("1.0", tk.END).strip().split("\n") if u.strip()]
        urls = [u for u in entries if is_valid_url(u)]
        invalid = [u for u in entries if not is_valid_url(u)]
        if not urls:
            return messagebox.showwarning("Advertencia", "Debes ingresar al menos una URL.")
        if self._scraping:
            return messagebox.showinfo("Info", "Ya hay un scraping en curso.")
        
        # Guardar automáticamente la configuración al iniciar
        self._save_config()
        
        threading.Thread(target=self._run_scraper, args=(urls, invalid), daemon=True).start()

    def _run_scraper(self, urls, invalid=None):
        self._scraping = True
        self.log("🔵 Iniciando scraping…")
        scraper_ebay.set_credentials(self.entry_oxy_user.get().strip(), self.entry_oxy_pass.get().strip())
        scraper_ebay.set_logger(self.log)  # retry/fallos de Oxylabs también al log del UI

        csv_path = self._batch_csv_path()
        self.log(f"📂 Reporte de este batch: {os.path.basename(csv_path)}")
        csv_ids_csv = self._get_csv_item_ids(csv_path)
        csv_ids_sql = dd.known_ids()
        csv_ids = csv_ids_csv | csv_ids_sql
        if csv_ids: self.log(f"📋 {len(csv_ids)} IDs ya registrados → se omitirán")

        resultados = []

        def procesar(url, idx, total, etapa=""):
            """Scrapea una URL, acumula en resultados. Devuelve True si trajo/encontró datos."""
            self.log(f"\n🔍 {etapa}[{idx}/{total}] {url}")
            try:
                if known_single_item_key(url, csv_ids):
                    self.log("   ⏭️ Este item ya está scrapeado; no se agregará al CSV (0 requests)")
                    return True
                failed_items = []
                df = self._dispatch(url, existing_ids=csv_ids, failed_out=failed_items)
                if failed_items:
                    fallidos.extend(failed_items)
                    self.log(f"   ⏳ {len(failed_items)} item(s) sin datos, van a cola de reintento")
                if df is None:
                    self.log("   ⚠️ Sin datos")
                    return bool(failed_items)
                if df.empty:
                    self.log("   ℹ️ Nada nuevo, todo ya en DB")
                    return True
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

        # Oxylabs reintenta errores de transporte; esta cola cubre HTML válido pero no parseable.
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
                    pd.concat([df_existing, df_new], ignore_index=True).to_csv(csv_path, index=False, encoding="utf-8-sig")
                    self.log(f"\n✅ +{nuevos} nuevos → {os.path.basename(csv_path)}")
                else:
                    self.log(f"\nℹ️ Sin items nuevos")
            else:
                nuevos = len(df_new)
                df_new.to_csv(csv_path, index=False, encoding="utf-8-sig")
                self.log(f"\n✅ {nuevos} items → {os.path.basename(csv_path)}")
            self._update_latest_info()
            n_new_db = dd.record_df(df_new)
            self.log(f"+{n_new_db} items agregados a la db")
            self._load_sellers()
        else:
            self.log("\n⚠️ No se obtuvieron resultados nuevos.")

        if fallidos:
            self.log(f"\n⚠️ {len(fallidos)} URL(s) sin datos tras reintentar:")
            for u in fallidos:
                self.log(f"   • {u}")
            df_failed = pd.DataFrame([
                {c: u if c == "URL" else FAILED_NOTE for c in scraper_ebay.COLUMNS}
                for u in fallidos
            ])
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            if os.path.exists(csv_path):
                df_existing = pd.read_csv(csv_path)
                existing_urls = set(str(s) for s in df_existing["URL"].dropna())
                df_failed = df_failed[~df_failed["URL"].isin(existing_urls)]
                if not df_failed.empty:
                    pd.concat([df_existing, df_failed], ignore_index=True).to_csv(csv_path, index=False, encoding="utf-8-sig")
            else:
                df_failed.to_csv(csv_path, index=False, encoding="utf-8-sig")
            if not df_failed.empty:
                self.log(f"   ➕ {len(df_failed)} fila(s) '{FAILED_NOTE}' agregadas al CSV")

        if invalid:
            self.log(f"\n⚠️ {len(invalid)} entrada(s) ignoradas porque no son URLs válidas:")
            for value in invalid:
                self.log(f"   • {value}")

        if nuevos:
            self._set_status(f"✅ Batch listo: +{nuevos} items → {os.path.basename(csv_path)}")
        else:
            self._set_status("✅ Batch listo: sin items nuevos")
        self._scraping = False

    def _dispatch(self, url, existing_ids=None, failed_out=None):
        low = url.lower()
        if "ebay" in low: return scraper_ebay.scrape_url(url, increment_usage_callback=self._increment_usage, existing_ids=existing_ids, failed_out=failed_out)
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
        save_settings(settings)
        self._update_latest_info()
        self._update_usage_ui()

if __name__ == "__main__":
    root = tk.Tk()
    sv_ttk.set_theme("dark")
    app = GrailzeeApp(root)
    root.mainloop()
