import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import threading
import os
import json
import pandas as pd

# === IMPORTA SCRIPTS ORIGINALES ===
import scraper_ebay
import scraper_chrono24
from google_loader import connect_to_spreadsheet, get_sheet_names, load_sheet_data, extract_ebay_links
from scraper_vendedor import get_first_seller_store_url  # <- solo devuelve el primer vendedor
#from scraper_vendedor import get_all_sellers  # <-- Nueva función
from Nuevos_Clientes import obtener_lista_productos
from google_loader import load_customers_dict, get_customer_url

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


CONFIG_FILE = "settings.json"

# =============================================================================
#                                CONFIGURACIÓN
# =============================================================================
def load_settings():
    if not os.path.exists(CONFIG_FILE):
        default = {
            "report_dir": "reportes",
            "prefix": "reporte",
            "auto_folder": True,
            "log_level": "normal",
            "pause": 1,
            "threads": 3,
            "credentials_path": "credentials.json",
            "theme": "light"
        }
        save_settings(default)
        return default

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_settings(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


settings = load_settings()

# =============================================================================
#                          APLICACIÓN PRINCIPAL (3 TABS)
# =============================================================================
class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Scraper Suite Pro - eBay / Chrono24 / Google Sheets")
        self.root.geometry("1150x800")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        # Tabs
        self.tab_scraper = ttk.Frame(notebook)
        self.tab_google = ttk.Frame(notebook)
        self.tab_config = ttk.Frame(notebook)

        notebook.add(self.tab_scraper, text="Scraper")
        notebook.add(self.tab_google, text="Google Sheets")
        notebook.add(self.tab_config, text="Configuración")

        # Construir las tres pestañas
        self.build_scraper_tab()
        self.build_google_tab()
        self.build_config_tab()

        # atributos para uso posterior
        self.sheet = None
        self.df = None
        self.df_combined = None  # usado cuando el usuario pide varias hojas

    # =============================================================================
    # TAB 1 – SCRAPER
    # =============================================================================
    def build_scraper_tab(self):
        tab = self.tab_scraper
        ttk.Label(tab, text="URLs (una por línea):", font=("Arial", 12)).pack(pady=10)
        self.txt_urls = scrolledtext.ScrolledText(tab, width=100, height=10)
        self.txt_urls.pack(pady=10)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Iniciar Scraping", command=self.start_scraper).grid(row=0, column=0, padx=10)
        ttk.Button(btn_frame, text="Limpiar", command=lambda: self.txt_urls.delete("1.0", tk.END)).grid(row=0, column=1, padx=10)

        ttk.Label(tab, text="Log:", font=("Arial", 12)).pack(pady=5)
        self.txt_log_scraper = scrolledtext.ScrolledText(tab, width=100, height=18, state="disabled")
        self.txt_log_scraper.pack(pady=10)

    def log_scraper(self, text):
        self.txt_log_scraper.config(state="normal")
        self.txt_log_scraper.insert(tk.END, text + "\n")
        self.txt_log_scraper.see(tk.END)
        self.txt_log_scraper.config(state="disabled")

    def start_scraper(self):
        urls = self.txt_urls.get("1.0", tk.END).strip().split("\n")
        urls = [u.strip() for u in urls if u.strip()]
        if not urls:
            return messagebox.showwarning("Advertencia", "Debes ingresar al menos una URL.")
        threading.Thread(target=self.run_scraper, args=(urls,), daemon=True).start()

    def run_scraper(self, urls):
        self.log_scraper("🔵 Iniciando scraping...\n")
        resultados = []

        for url in urls:
            self.log_scraper(f"🔍 Analizando: {url}")
            try:
                url_lower = url.lower()
                if "ebay" in url_lower:
                    df = scraper_ebay.scrape_url(url)
                elif "chrono24" in url_lower:
                    df = scraper_chrono24.scrape_multiple([url])
                else:
                    self.log_scraper("⚠️ Sitio no reconocido (no es eBay ni Chrono24)\n")
                    continue

                if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
                    resultados.append(df)
                    self.log_scraper("✔ OK")
                else:
                    self.log_scraper("⚠️ Sin datos\n")
            except Exception as e:
                self.log_scraper(f"❌ Error: {e}")

        if resultados:
            df_final = pd.concat(resultados, ignore_index=True)
            df_final.dropna(how="all", inplace=True)

            if not os.path.exists(settings["report_dir"]):
                os.makedirs(settings["report_dir"])

            filename = f"{settings['report_dir']}/{settings['prefix']}_scraper.csv"
            df_final.to_csv(filename, index=False)
            self.log_scraper(f"\n✅ Resultados guardados en {filename}")
        else:
            self.log_scraper("\n⚠️ No se obtuvieron resultados.")

    # =============================================================================
    # TAB 2 – GOOGLE SHEETS
    # =============================================================================
    def build_google_tab(self):
        tab = self.tab_google

        frame = ttk.Frame(tab)
        frame.pack(pady=15)

        ttk.Label(frame, text="URL Google Sheet:").grid(row=0, column=0, padx=5)
        self.entry_sheet = ttk.Entry(frame, width=70)
        self.entry_sheet.grid(row=0, column=1)
        ttk.Button(frame, text="Conectar", command=self.connect_sheet).grid(row=0, column=2, padx=5)

        ttk.Label(frame, text="Hoja:").grid(row=1, column=0)
        self.combo_sheets = ttk.Combobox(frame, width=40)
        self.combo_sheets.grid(row=1, column=1)

        # ============================
        # REUBICADO — antes del botón Cargar
        # ============================
        ttk.Label(tab, text="Cliente (URL o nombre):", font=("Arial", 12)).pack(pady=5)
        self.entry_customer = ttk.Entry(tab, width=80)
        self.entry_customer.pack()


        ttk.Button(frame, text="Cargar", command=self.load_sheet).grid(row=1, column=2)

        ttk.Label(tab, text="Vista previa:", font=("Arial", 12)).pack(pady=5)
        self.preview = scrolledtext.ScrolledText(tab, width=120, height=12, state="disabled")
        self.preview.pack()

        frame_botones = ttk.Frame(tab)
        frame_botones.pack(pady=10)

        frame2 = ttk.Frame(tab)
        frame2.pack(pady=10)
        ttk.Button(frame2, text="Cliente Nuevo", command=lambda: self.run_gscraper("nuevo")).grid(row=0, column=0, padx=10)
        ttk.Button(frame2, text="Cliente Recurrente", command=lambda: self.run_gscraper("recurrente")).grid(row=0, column=1, padx=10)

        ttk.Label(tab, text="Log:", font=("Arial", 12)).pack()
        self.txt_log_google = scrolledtext.ScrolledText(tab, width=120, height=12, state="disabled")
        self.txt_log_google.pack()

    def log_google(self, text):
        self.txt_log_google.config(state="normal")
        self.txt_log_google.insert(tk.END, text + "\n")
        self.txt_log_google.see(tk.END)
        self.txt_log_google.config(state="disabled")

    def connect_sheet(self):
        try:
            url = self.entry_sheet.get().strip()
            if not url:
                return messagebox.showwarning("Atención", "Introduce una URL de Google Sheets.")

            self.sheet = connect_to_spreadsheet(url)
            sheets = get_sheet_names(self.sheet)
            self.combo_sheets["values"] = sheets

            if sheets:
                self.combo_sheets.current(0)

            self.log_google("✔ Conectado correctamente.")

            # Inicializar lista vacía de URLs
            self.ebay_links_loaded = []

            # Cargar automáticamente la hoja 'Customers' si existe
            customers_sheet_name = None
            for s in sheets:
                if s.lower() == "customers":
                    customers_sheet_name = s
                    break

            if not customers_sheet_name:
                self.customers_dict = {}
                self.log_google("⚠ No existe la hoja 'Customers'.")
                return

            self.df_customers = load_sheet_data(self.sheet, customers_sheet_name)
            self.customers_dict = load_customers_dict(self.df_customers)

            if self.customers_dict:
                # no llenamos combo; dejamos la Entry vacía hasta que el usuario cargue una hoja
                self.entry_customer.delete(0, tk.END)
                self.log_google(f"✔ Hoja 'Customers' cargada. {len(self.customers_dict)} clientes disponibles.")
            else:
                self.log_google("⚠ No se pudieron cargar clientes desde 'Customers'.")

        except Exception as e:
            messagebox.showerror("Error", e)


    def load_sheet(self):
        try:
            name = self.combo_sheets.get()
            if not name:
                return messagebox.showwarning("Atención", "Selecciona una hoja.")

            self.df = load_sheet_data(self.sheet, name)

            # Vista previa
            self.preview.config(state="normal")
            self.preview.delete("1.0", tk.END)
            self.preview.insert(tk.END, self.df.head(15).to_string(index=False))
            self.preview.config(state="disabled")

            self.log_google(f"✔ Hoja '{name}' cargada.")

            # EXTRAER LINKS DE EBAY (todas las hojas)
            if self.df is not None and not self.df.empty:
                links = extract_ebay_links(self.df)

                if links:
                    self.ebay_links_loaded = links  # Para Cliente Recurrente

                    with open("google_ebay_links.txt", "w", encoding="utf-8") as f:
                        for link in links:
                            f.write(link + "\n")

                    self.log_google(f"✔ {len(links)} links de eBay guardados en 'google_ebay_links.txt'")

            # --- NUEVO: si el nombre de la hoja coincide con un Account en customers_dict,
            # rellenar la Entry con la URL correspondiente ---
            try:
                if hasattr(self, "customers_dict") and self.customers_dict:
                    # buscar por nombre de hoja exacto
                    url = get_customer_url(name, self.customers_dict)
                    if url:
                        # si get_customer_url devolvió una URL, mostrarla
                        self.entry_customer.delete(0, tk.END)
                        self.entry_customer.insert(0, url)
                        self.log_google(f"✔ Cliente asociado a hoja '{name}' encontrado y Entry actualizado.")
                    else:
                        # si no hay coincidencia, limpiar Entry (opcional)
                        self.entry_customer.delete(0, tk.END)
                        self.log_google(f"⚠ No se encontró cliente asociado a la hoja '{name}'. Entry vacía.")
            except Exception as e:
                self.log_google(f"⚠ Error buscando cliente para la hoja '{name}': {e}")

        except Exception as e:
            messagebox.showerror("Error", e)

    def detect_vendors(self):
        if self.df is None:
            return messagebox.showwarning("Atención", "Carga primero una hoja.")

        # Extraer links y filtrar vacíos
        links = [str(l) for l in extract_ebay_links(self.df) if l]

        if not links:
            self.log_google("⚠️ No se encontraron links de eBay")
            return

        # Eliminar duplicados exactos
        links = list(dict.fromkeys(links))

        self.log_google(f"🔵 Iniciando detección de vendedores para {len(links)} productos...")

        def run_scraper_vendedor():
            try:
                tiendas = {}
                for link in links:
                    store_url = get_first_seller_store_url([link])
                    if store_url and store_url not in tiendas.values():
                        tiendas[link] = store_url

                self.list_vendors.delete(0, tk.END)
                if tiendas:
                    for store in tiendas.values():
                        self.list_vendors.insert(tk.END, store)
                        self.log_google(f"✔ Vendedor detectado: {store}")
                else:
                    self.log_google("⚠️ No se encontró ningún vendedor")

            except Exception as e:
                self.log_google(f"❌ Error detectando vendedores: {e}")

        threading.Thread(target=run_scraper_vendedor, daemon=True).start()

    def add_manual_vendor(self):
        vendor = simpledialog.askstring("Agregar vendedor", "Escribe la URL de Ebay del vendedor:")
        if vendor:
            self.list_vendors.insert(tk.END, vendor)
            self.log_google(f"✔ Vendedor agregado manualmente: {vendor}")

    # =============================================================================
    # SISTEMA CLIENTE NUEVO / RECURRENTE (usa obtener_lista_productos)
    # =============================================================================
    def run_gscraper(self, tipo):
        # El Entry ahora puede contener la URL directamente o un nombre de cliente.
        entry_val = self.entry_customer.get().strip()

        if not entry_val:
            return messagebox.showwarning("Atención", "Debes indicar el cliente (URL o nombre).")

        # Si el usuario puso una URL (empieza con http), la usamos directamente
        if entry_val.lower().startswith("http"):
            url_cliente = entry_val
        else:
            # si puso un nombre, buscamos en el diccionario
            url_cliente = get_customer_url(entry_val, getattr(self, "customers_dict", {}))

        if not url_cliente:
            return messagebox.showerror("Error", f"El cliente '{entry_val}' no existe o no tiene URL asociada en 'Customers'.")

        # Solicitar número de páginas si es recurrente
        paginas = None
        if tipo == "recurrente":
            paginas = simpledialog.askinteger(
                "Número de páginas",
                "¿Cuántas páginas deseas scrapear? (1–50)",
                minvalue=1,
                maxvalue=50
            )
            if not paginas:
                return

        # Iniciar scraping en hilo
        threading.Thread(
            target=self._run_gscraper_thread,
            args=(tipo, url_cliente, paginas),
            daemon=True
        ).start()


    # ================================================================
    # NUEVA FUNCIÓN: Verificar si la URL de eBay está bloqueada
    # ================================================================
    def test_ebay_url(self, url, timeout=12):
        """
        Abre la URL en Chrome con Selenium y detecta bloqueos, CAPTCHA o IP restringida.
        Retorna: (blocked: bool, message: str)
        """
        driver = None
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")  # modo incógnito sin UI
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(options=options)
            driver.get(url)

            try:
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                return True, "⛔ Timeout: eBay no cargó. Probable bloqueo por IP."

            html = driver.page_source.lower()
            if "captcha" in html or "enter the characters" in html:
                return True, "⚠ CAPTCHA detectado. Cambia de VPN."
            if "access denied" in html:
                return True, "⛔ Acceso denegado por eBay. Cambia de VPN."
            if "403 forbidden" in html:
                return True, "⛔ Error 403: IP bloqueada. Cambia de VPN."
            if "why did this happen" in html:
                return True, "⛔ eBay bloqueó el acceso humano. Cambia de VPN."
            if len(html) < 5000:
                return True, "⚠ Página demasiado corta. Probable bloqueo regional."

            return False, "🟢 Acceso OK. La IP no está bloqueada."

        except WebDriverException as e:
            return True, f"❌ Error Selenium: {e}"

        finally:
            if driver:
                driver.quit()


    # ================================================================
    # MODIFICACIÓN: _run_gscraper_thread
    # ================================================================
    def _run_gscraper_thread(self, tipo, vendedor, paginas):
        self.log_google(f"🔵 Procesando cliente: {vendedor}")

        # --- SOLO PARA CLIENTES NUEVOS ---
        if tipo == "nuevo":
            blocked, msg = self.test_ebay_url(vendedor)
            self.log_google(f"⚠ Verificación eBay: {msg}")
            if blocked:
                self.log_google("❌ Bloqueo detectado. Cambia la VPN y vuelve a intentar.")
                return
            else:
                self.log_google("🟢 URL segura para scraping. Continuando...")


       # --- SCRAPING REAL ---
        try:
            productos = obtener_lista_productos(
                store_url=vendedor,
                archivo_salida="productos_extraidos.txt",
                num_paginas=paginas
            )

            if not productos:
                return self.log_google("⚠️ No se encontraron productos.")

            self.log_google(f"✔ Productos obtenidos: {len(productos)}")
            self.log_google("📝 Guardado en productos_extraidos.txt")

        except Exception as e:
            return self.log_google(f"❌ Error: {e}")


        # =========================================================
        # CLIENTE NUEVO → no comparar, terminar aquí
        # =========================================================
        if tipo == "nuevo":
            return

        # =========================================================
        # CLIENTE RECURRENTE → COMPARAR CON GOOGLE SHEET
        # =========================================================
        if not hasattr(self, "ebay_links_loaded"):
            return self.log_google("❌ Primero carga una hoja de Google Sheet.")

        previos = set(self.ebay_links_loaded)
        nuevos = [p for p in productos if p not in previos]

        self.log_google(f"🔍 Comparando contra {len(previos)} URLs anteriores...")

        if nuevos:
            self.log_google(f"🆕 Se encontraron {len(nuevos)} productos nuevos:")
            for n in nuevos:
                self.log_google(f"   → {n}")

            with open("nuevos_productos.txt", "w", encoding="utf-8") as f:
                for n in nuevos:
                    f.write(n + "\n")

            self.log_google("📁 Archivo generado: nuevos_productos.txt")

        else:
            self.log_google("✔ No hay productos nuevos.")


    # =============================================================================
    # TAB 3 – CONFIGURACIÓN
    # =============================================================================
    def build_config_tab(self):
        tab = self.tab_config
        ttk.Label(tab, text="Configuración General", font=("Arial", 14, "bold")).pack(pady=10)

        frame = ttk.Frame(tab)
        frame.pack(pady=10)
        ttk.Label(frame, text="Carpeta de reportes:").grid(row=0, column=0, padx=5)
        self.entry_report_dir = ttk.Entry(frame, width=50)
        self.entry_report_dir.grid(row=0, column=1)
        self.entry_report_dir.insert(0, settings["report_dir"])
        ttk.Button(frame, text="Cambiar", command=self.choose_folder).grid(row=0, column=2, padx=5)

        frame2 = ttk.Frame(tab)
        frame2.pack(pady=10)
        ttk.Label(frame2, text="Prefijo del archivo:").grid(row=0, column=0, padx=5)
        self.entry_prefix = ttk.Entry(frame2, width=40)
        self.entry_prefix.grid(row=0, column=1)
        self.entry_prefix.insert(0, settings["prefix"])

        frame3 = ttk.Frame(tab)
        frame3.pack(pady=10)
        ttk.Label(frame3, text="Número de hilos:").grid(row=0, column=0, padx=5)
        self.spin_threads = tk.Spinbox(frame3, from_=1, to=20, width=5)
        self.spin_threads.grid(row=0, column=1)
        self.spin_threads.delete(0, tk.END)
        self.spin_threads.insert(0, settings["threads"])

        frame4 = ttk.Frame(tab)
        frame4.pack(pady=10)
        ttk.Label(frame4, text="Pausa entre requests (segundos):").grid(row=0, column=0, padx=5)
        self.spin_pause = tk.Spinbox(frame4, from_=0, to=10, increment=0.5, width=5)
        self.spin_pause.grid(row=0, column=1)
        self.spin_pause.delete(0, tk.END)
        self.spin_pause.insert(0, settings["pause"])

        ttk.Button(tab, text="Guardar configuración", command=self.save_config).pack(pady=20)

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_report_dir.delete(0, tk.END)
            self.entry_report_dir.insert(0, folder)

    def save_config(self):
        new_settings = {
            "report_dir": self.entry_report_dir.get(),
            "prefix": self.entry_prefix.get(),
            "auto_folder": settings["auto_folder"],
            "log_level": settings["log_level"],
            "pause": float(self.spin_pause.get()),
            "threads": int(self.spin_threads.get()),
            "credentials_path": settings["credentials_path"],
            "theme": settings["theme"]
        }
        save_settings(new_settings)
        messagebox.showinfo("Guardado", "Configuración actualizada correctamente.")


# =============================================================================
# EJECUCIÓN DE LA APP
# =============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
