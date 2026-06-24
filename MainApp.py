import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import os
import json
import re
import glob
import pandas as pd
import sv_ttk

# === SCRAPERS ===
import scraper_ebay
import scraper_chrono24
import scraper_swisstimepiececo
import Scraper_Wywatl
import Scraper_Thewatchoutlet
import Scraper_Grandcaliber
import Scraper_Boknowsluxury
import Scraper_Timepieceperfection

CONFIG_FILE = "settings.json"

def load_settings():
    if not os.path.exists(CONFIG_FILE):
        default = {"report_dir": "reportes", "prefix": "reporte", "oxy_usage": {}}
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

def extract_vendor_name(url):
    m = re.search(r'[?&]_ssn=([^&]+)', url, re.IGNORECASE)
    if m: return m.group(1).strip()
    m = re.search(r'[?&]store_name=([^&]+)', url, re.IGNORECASE)
    if m: return m.group(1).strip()
    m = re.search(r'/str/([^/?#]+)', url)
    if m: return m.group(1).strip()
    return None

class GrailzeeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Grailzee Scraper")
        self.root.geometry("1200x820")
        self.root.minsize(900, 650)
        self._scraping = False
        self._build_ui()
        self._refresh_csvs()
        self._update_usage_ui()

    def _build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=16, pady=(12, 4))

        ttk.Label(top, text="⌚ Grailzee Scraper", font=("Segoe UI", 18, "bold")).pack(side="left")
        
        self.lbl_usage = ttk.Label(top, text="Oxylabs Req: 0", font=("Segoe UI", 10))
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

        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x", pady=(0, 12))
        self.btn_scrape = ttk.Button(btn_row, text="🚀  Iniciar Scraping", command=self.start_scraper)
        self.btn_scrape.pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Limpiar", command=lambda: self.txt_urls.delete("1.0", tk.END)).pack(side="left", padx=(0, 6))

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)

        ttk.Label(left, text="Reportes CSV", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))
        csv_row = ttk.Frame(left)
        csv_row.pack(fill="x", pady=(0, 4))
        self.combo_csv = ttk.Combobox(csv_row, width=32)
        self.combo_csv.pack(side="left", padx=(0, 4))
        self.combo_csv.bind("<<ComboboxSelected>>", lambda e: self._on_csv_selected())
        ttk.Button(csv_row, text="🔄", width=3, command=self._refresh_csvs).pack(side="left", padx=(0, 4))
        ttk.Button(csv_row, text="📂 Abrir", width=8, command=self._open_csv_folder).pack(side="left")

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

        pfx_row = ttk.Frame(left)
        pfx_row.pack(fill="x", pady=(0, 4))
        ttk.Label(pfx_row, text="Prefijo archivo:").pack(side="left", padx=(0, 4))
        self.entry_prefix = ttk.Entry(pfx_row, width=20)
        self.entry_prefix.pack(side="left")
        self.entry_prefix.insert(0, settings.get("prefix", "reporte"))

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
        self.lbl_usage.config(text=f"Oxylabs Req: {count} (~${(count / 1000) * 1.5:.2f} USD)")

    def _increment_usage(self):
        user = self.entry_oxy_user.get().strip()
        if user:
            usage_dict = settings.get("oxy_usage", {})
            usage_dict[user] = usage_dict.get(user, 0) + 1
            settings["oxy_usage"] = usage_dict
            self.root.after(0, self._update_usage_ui)

    def _refresh_csvs(self):
        report_dir = settings.get("report_dir", "reportes")
        os.makedirs(report_dir, exist_ok=True)
        csvs = sorted(glob.glob(os.path.join(report_dir, "*.csv")))
        names = [os.path.basename(c) for c in csvs]
        current = self.combo_csv.get()
        self.combo_csv["values"] = names
        if current in names:
            self.combo_csv.set(current)
        elif names:
            self.combo_csv.current(0)
        self._on_csv_selected()

    def _on_csv_selected(self):
        name = self.combo_csv.get()
        if not name:
            self.lbl_csv_info.config(text="  Sin reportes aún")
            return
        report_dir = settings.get("report_dir", "reportes")
        path = os.path.join(report_dir, name)
        try:
            df = pd.read_csv(path)
            self.lbl_csv_info.config(text=f"  📋 {len(df)} items en {name}")
        except Exception:
            self.lbl_csv_info.config(text=f"  ⚠️ Error leyendo {name}")

    def _open_csv_folder(self):
        report_dir = os.path.abspath(settings.get("report_dir", "reportes"))
        os.makedirs(report_dir, exist_ok=True)
        import subprocess
        try:
            if os.name == 'nt':
                os.startfile(report_dir)
            else:
                subprocess.Popen(['xdg-open', report_dir])
        except Exception:
            self.log(f"📂 Carpeta: {report_dir}")

    def _get_csv_item_ids(self, csv_path):
        if not os.path.exists(csv_path):
            return set()
        try:
            df = pd.read_csv(csv_path)
            ids = set(str(s) for s in df["Stock"].dropna())
            if "URL" in df.columns:
                for url in df["URL"].dropna():
                    item_id = scraper_ebay.extract_item_id(str(url))
                    if item_id: ids.add(item_id)
            return ids
        except Exception:
            return set()

    def _auto_detect_csv(self, urls):
        report_dir = settings.get("report_dir", "reportes")
        for url in urls:
            vendor = extract_vendor_name(url)
            if vendor:
                csvs = self.combo_csv["values"] or []
                for csv_name in csvs:
                    if vendor.lower() in csv_name.lower():
                        self.combo_csv.set(csv_name)
                        self._on_csv_selected()
                        self.log(f"📂 CSV detectado: {csv_name}")
                        return os.path.join(report_dir, csv_name)
                target = f"{vendor}.csv"
                self.log(f"📂 Nuevo CSV se creará: {target}")
                return os.path.join(report_dir, target)
        selected = self.combo_csv.get()
        if selected:
            return os.path.join(report_dir, selected)
        prefix = settings.get("prefix", "reporte")
        return os.path.join(report_dir, f"{prefix}_scraper.csv")

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
        self.log("🔵 Iniciando scraping (Oxylabs)…")
        scraper_ebay.set_credentials(self.entry_oxy_user.get().strip(), self.entry_oxy_pass.get().strip())

        csv_path = self._auto_detect_csv(urls)
        csv_ids = self._get_csv_item_ids(csv_path)
        if csv_ids: self.log(f"📋 {len(csv_ids)} items ya en CSV → se omitirán")

        self._set_status(f"Scrapeando {len(urls)} URL(s)…")
        self.progress["value"] = 0
        self.progress["maximum"] = len(urls)
        resultados = []

        for i, url in enumerate(urls, 1):
            self.log(f"\n🔍 [{i}/{len(urls)}] {url}")
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
                else:
                    self.log("   ⚠️ Sin datos")
            except Exception as e:
                self.log(f"   ❌ Error: {e}")
            self.progress["value"] = i

        if resultados:
            df_new = pd.concat(resultados, ignore_index=True)
            df_new.dropna(how="all", inplace=True)
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            if os.path.exists(csv_path):
                df_existing = pd.read_csv(csv_path)
                existing_stocks = set(str(s) for s in df_existing["Stock"].dropna())
                df_new = df_new[~df_new["Stock"].astype(str).isin(existing_stocks)]
                if not df_new.empty:
                    pd.concat([df_existing, df_new], ignore_index=True).to_csv(csv_path, index=False)
                    self.log(f"\n✅ +{len(df_new)} nuevos → {os.path.basename(csv_path)}")
                else:
                    self.log(f"\nℹ️ Sin items nuevos")
            else:
                df_new.to_csv(csv_path, index=False)
                self.log(f"\n✅ {len(df_new)} items → {os.path.basename(csv_path)}")
            self._refresh_csvs()
            self.combo_csv.set(os.path.basename(csv_path))
            self._on_csv_selected()
        else:
            self.log("\n⚠️ No se obtuvieron resultados nuevos.")

        self._set_status("Listo.")
        self._scraping = False

    def _dispatch(self, url, existing_ids=None):
        low = url.lower()
        if "ebay" in low: return scraper_ebay.scrape_url(url, increment_usage_callback=self._increment_usage, existing_ids=existing_ids)
        if "chrono24" in low: return scraper_chrono24.scrape_multiple([url])
        if "swisstimepiececo" in low or "swiss timepiece" in low: return scraper_swisstimepiececo.scrape_url(url)
        if "wywatl" in low: return Scraper_Wywatl.scrape_url(url)
        if "thewatchoutlet" in low: return Scraper_Thewatchoutlet.scrape_url(url)
        if "grandcaliber" in low: return Scraper_Grandcaliber.scrape_url(url)
        if "boknowsluxury" in low: return Scraper_Boknowsluxury.scrape_url(url)
        if "timepieceperfection" in low: return Scraper_Timepieceperfection.scrape_url(url)
        self.log("   ⚠️ Sitio no reconocido")
        return None

    def _choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_report_dir.delete(0, tk.END)
            self.entry_report_dir.insert(0, folder)

    def _save_config(self):
        settings["report_dir"] = self.entry_report_dir.get()
        settings["prefix"] = self.entry_prefix.get()
        settings["oxy_user"] = self.entry_oxy_user.get()
        settings["oxy_pass"] = self.entry_oxy_pass.get()
        save_settings(settings)
        self._refresh_csvs()
        self._update_usage_ui()

if __name__ == "__main__":
    root = tk.Tk()
    sv_ttk.set_theme("dark")
    app = GrailzeeApp(root)
    root.mainloop()
