import requests
import time
import random
import re
import os
from typing import List

class eBaySearchScraperGUI:
    """
    Scraper de eBay optimizado para GUI.
    Recibe nombre o URL del vendedor desde la app.
    Evita prints y retorna lista de URLs, usa logger de GUI.
    """

    def __init__(self, seller_name: str, logger=None):
        self.seller_name = seller_name
        self.logger = logger or (lambda x: None)  # callback para logging en GUI
        self.session = self._create_session()
        self.request_count = 0
        self.all_items: List[str] = []
        self.start_time = time.time()

        # Configuración anti-bloqueo
        self.config = {
            'min_delay': 5,
            'max_delay': 10,
            'items_per_page': 240,
            'max_pages': 10,
            'search_url': 'https://www.ebay.com/sch/i.html',
        }

    def _log(self, text: str):
        """Callback de logging"""
        self.logger(text)

    def _create_session(self) -> requests.Session:
        """Crear sesión HTTP con headers de navegador"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        return session

    def _random_delay(self):
        """Delay aleatorio entre requests para simular humano"""
        delay = random.uniform(self.config['min_delay'], self.config['max_delay'])
        time.sleep(delay)

    def _make_search_request(self, page: int) -> str:
        """Request de búsqueda en eBay"""
        self.request_count += 1
        self._random_delay()

        params = {
            '_nkw': self.seller_name,
            '_sacat': '0',
            '_from': 'R40',
            '_pgn': page,
            '_ipg': str(self.config['items_per_page']),
            '_sop': '12',  # Best Match
            'rt': 'nc',
            'LH_Sold': '0',
            'LH_Complete': '0',
            '_dmd': '2',
        }

        try:
            resp = self.session.get(self.config['search_url'], params=params, timeout=20)
            if resp.status_code == 200 and len(resp.text) > 50000:
                return resp.text
            return ""
        except Exception:
            return ""

    def _extract_items_from_search(self, html: str) -> List[str]:
        """Extraer URLs de items de eBay desde HTML"""
        items = []
        pattern = r'href="(https://www\.ebay\.com/itm/[^"?]+)'
        matches = re.findall(pattern, html)
        for m in matches:
            url = m.split('?')[0]
            if url not in items:
                items.append(url)
        return items

    def scrape_by_search(self, max_pages: int = None) -> List[str]:
        """Scraping completo, paginación automática"""
        max_pages = max_pages or self.config['max_pages']
        self._log(f"🔎 Scraping vendedor '{self.seller_name}' hasta {max_pages} páginas...")

        for page in range(1, max_pages + 1):
            html = self._make_search_request(page)
            if not html:
                self._log(f"⚠ Página {page} vacía o bloqueada, saltando...")
                continue

            page_items = self._extract_items_from_search(html)
            new_items = [i for i in page_items if i not in self.all_items]

            self.all_items.extend(new_items)
            self._log(f"📄 Página {page}: {len(new_items)} items nuevos encontrados")

            # Detecta fin de resultados temprano
            if "no results found" in html.lower() and page > 1:
                break

        self._log(f"✔ Scraping terminado. Total items: {len(self.all_items)}")
        return self.all_items


def obtener_lista_productos(store_url: str, archivo_salida: str = "productos_extraidos.txt",
                            num_paginas: int = 5, logger=None) -> List[str]:
    """
    Función para MainApp.py
    Recibe URL o nombre de vendedor desde Entry, retorna lista de URLs
    y guarda en archivo.
    """
    # Si es URL tipo https://www.ebay.com/str/seller, extraer nombre
    if store_url.startswith("http"):
        seller_name = store_url.rstrip("/").split("/")[-1]
    else:
        seller_name = store_url

    scraper = eBaySearchScraperGUI(seller_name, logger=logger)
    productos = scraper.scrape_by_search(max_pages=num_paginas)

    # Guardar resultados
    if productos:
        os.makedirs(os.path.dirname(archivo_salida) or ".", exist_ok=True)
        with open(archivo_salida, 'w', encoding='utf-8') as f:
            for p in productos:
                f.write(p + "\n")
        if logger:
            logger(f"💾 Guardado {len(productos)} productos en {archivo_salida}")

    return productos
