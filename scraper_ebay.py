import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
import requests
import urllib.parse as uparse
from bs4 import BeautifulSoup
import pandas as pd

COLUMNS = [
    "Stock", "URL", "Make", "Model", "Reference Number", "Year", "Box", "Papers", "Original Price"
]
MISSING = "Missing information"

LABEL_MAP = {
    "estado": "Status", "status": "Status", "estado del articulo": "Status", "condition": "Status",
    "make": "Make", "marca": "Make", "brand": "Make",
    "model": "Model", "modelo": "Model", "series": "Model", "serie": "Model", "model name": "Model", "nombre del modelo": "Model",
    "reference number": "Reference Number", "reference": "Reference Number", "reference no.": "Reference Number",
    "número de referencia": "Reference Number", "numero de referencia": "Reference Number",
    "year": "Year", "año": "Year", "ano": "Year", "year manufactured": "Year",
    "box": "Box", "caja": "Box", "with original box": "Box", "with original box/packaging": "Box",
    "papers": "Papers", "papeles": "Papers", "documentación": "Papers", "documentation": "Papers",
    "with papers": "Papers",
}

REQUEST_DELAY = 1.0

# Oxylabs Credentials - Will be injected by MainApp
OXYLABS_USERNAME = ""
OXYLABS_PASSWORD = ""
OXYLABS_API_URL = "https://realtime.oxylabs.io/v1/queries"
OXYLABS_LOG_PATH = "logs/oxylabs_errors.txt"

def set_credentials(user, pwd):
    global OXYLABS_USERNAME, OXYLABS_PASSWORD
    OXYLABS_USERNAME = user
    OXYLABS_PASSWORD = pwd

def empty_result():
    return pd.DataFrame(columns=COLUMNS)

def _oxylabs_failure_reason(status_code: int) -> str:
    if status_code in (401, 403):
        return "invalid_credentials"
    if status_code == 402:
        return "account_limit_or_billing"
    if status_code == 429:
        return "rate_limited"
    return "provider_error"

def _oxylabs_user_message(reason: str) -> str:
    messages = {
        "missing_credentials": "Oxylabs no configurado. Agrega usuario y contrasena.",
        "invalid_credentials": "Oxylabs rechazo las credenciales. Revisa usuario/contrasena o solicita nuevas credenciales.",
        "account_limit_or_billing": "Oxylabs no tiene saldo o alcanzo el limite. Solicita nuevas credenciales o revisa el panel de Oxylabs.",
        "rate_limited": "Oxylabs alcanzo un limite temporal. Espera unos minutos o revisa el panel de Oxylabs.",
        "provider_error": "Oxylabs no pudo obtener datos. Revisa credenciales, saldo o el panel de Oxylabs.",
        "empty_content": "Oxylabs respondio sin contenido util para esta URL.",
        "network_error": "No se pudo conectar con Oxylabs. Revisa la conexion e intenta de nuevo.",
    }
    return messages.get(reason, messages["provider_error"])

def _safe_log_url(url: str) -> str:
    parsed = uparse.urlparse(url)
    return uparse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

def _log_oxylabs_failure(url: str, reason: str, status_code: int | None = None, detail: str = "") -> None:
    Path(OXYLABS_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    status_text = "" if status_code is None else f" status={status_code}"
    detail_text = "" if not detail else f" detail_type={detail}"
    message = _oxylabs_user_message(reason)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with open(OXYLABS_LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} reason={reason}{status_text} url={_safe_log_url(url)} message={message}{detail_text}\n")

def normalize_label(label):
    normalized = re.sub(r"\s+", " ", label.strip().lower())
    if normalized.endswith(":"):
        normalized = normalized[:-1].strip()
    return LABEL_MAP.get(normalized)

def extract_item_id(url):
    m = re.search(r"/itm/(\d+)", url)
    return m.group(1) if m else None

def is_item_url(url):
    return extract_item_id(url) is not None

def is_search_or_store_url(url):
    lower = url.lower()
    return ("ebay.com/sch/" in lower or "ebay.com/str/" in lower or 
            "_ssn=" in lower or "store_name=" in lower or "_nkw=" in lower)

# =========================
# OXYLABS CLIENT
# =========================
def fetch_oxylabs_html(url, increment_usage_callback: Callable[[], None] | None = None):
    if not OXYLABS_USERNAME or not OXYLABS_PASSWORD:
        reason = "missing_credentials"
        _log_oxylabs_failure(url, reason)
        print(f"⚠️ {_oxylabs_user_message(reason)}")
        return None

    try:
        response = requests.post(
            OXYLABS_API_URL,
            auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
            json={"source": "universal", "url": url, "geo_location": "United States"},
            timeout=60,
        )
        if response.status_code != 200:
            reason = _oxylabs_failure_reason(response.status_code)
            _log_oxylabs_failure(url, reason, response.status_code)
            print(f"⚠️ {_oxylabs_user_message(reason)}")
            return None
            
        if increment_usage_callback:
            increment_usage_callback()

        results = response.json().get("results", [])
        if not results:
            reason = "empty_content"
            _log_oxylabs_failure(url, reason, response.status_code)
            print(f"⚠️ {_oxylabs_user_message(reason)}")
            return None
        content = results[0].get("content")
        if not content:
            reason = "empty_content"
            _log_oxylabs_failure(url, reason, response.status_code)
            print(f"⚠️ {_oxylabs_user_message(reason)}")
            return None
        return content
    except requests.RequestException as e:
        reason = "network_error"
        _log_oxylabs_failure(url, reason, detail=type(e).__name__)
        print(f"❌ {_oxylabs_user_message(reason)}")
        return None

# =========================
# PARSEO HTML
# =========================
def detect_box_papers(specs):
    box, papers = "No", "No"
    for label, value in specs.items():
        label_text, value_text = label.lower(), value.strip().lower()
        has_negative = re.search(r"\b(no|without|none)\b", value_text)
        if not has_negative and any(k in label_text or k in value_text for k in ["box", "caja", "pack", "embalaje"]):
            box = "Yes"
        if not has_negative and any(k in label_text or k in value_text for k in ["papers", "papeles", "documentación", "documentation"]):
            papers = "Yes"
    return box, papers

def _first_spec(specs, canonical_label):
    for label, value in specs.items():
        if normalize_label(label) == canonical_label:
            return value
    return MISSING

def parse_item_html(html, url):
    soup = BeautifulSoup(html, "html.parser")
    labels = soup.select("dt.ux-labels-values__labels")
    values = soup.select("dd.ux-labels-values__values")
    specs = {l.get_text(" ", strip=True): v.get_text(" ", strip=True) for l, v in zip(labels, values)}
    
    box_value, papers_value = detect_box_papers(specs)
    
    year = _first_spec(specs, "Year")
    if year == MISSING or re.search(r"\b(mm|cm|inch)\b", year.lower()):
        title_el = soup.select_one("h1.x-item-title__mainTitle span") or soup.select_one("h1")
        year = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", title_el.get_text(" ", strip=True)).group() if (title_el and re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", title_el.get_text(" ", strip=True))) else MISSING
    
    price_el = soup.select_one('div[data-testid="x-price-primary"] span') or soup.select_one("div.x-bin-price span")
    price = MISSING
    if price_el:
        raw_price = price_el.get_text(" ", strip=True).replace("\u00a0", " ").strip("() ")
        price_match = re.search(r"(?:US\s*)?\$\s?[\d\s.,]+", raw_price)
        price = price_match.group(0).replace(" ", "") if price_match else raw_price

    stock_el = soup.select_one("div.ux-layout-section__textual-display--itemId span.ux-textspans--BOLD")
    stock = stock_el.get_text(" ", strip=True) if stock_el else extract_item_id(url) or MISSING

    item = {
        "Stock": stock, "URL": url,
        "Make": _first_spec(specs, "Make"), "Model": _first_spec(specs, "Model"),
        "Reference Number": _first_spec(specs, "Reference Number"),
        "Year": year, "Box": box_value, "Papers": papers_value, "Original Price": price,
    }
    return pd.DataFrame([item], columns=COLUMNS)

# =========================
# PARSEO BUSQUEDA/TIENDA
# =========================
def extract_item_links_from_search_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    seen, urls = set(), []
    for a in soup.find_all('a'):
        href = a.get('href')
        if not href or '/itm/' not in href: continue
        card = a.find_parent(['li', 'article'])
        if not card: continue
        card_classes = ' '.join(card.get('class', []))
        if not any(c in card_classes for c in ['s-card', 's-item', 'str-item-card', 'StoreFrontItemCard']): continue
        
        title_element = card.select_one('.s-card__title, .s-item__title')
        if title_element and title_element.get_text(' ', strip=True).lower() == 'shop on ebay': continue
        
        clean = href.split('?')[0]
        if clean not in seen and '123456' not in clean:
            seen.add(clean)
            urls.append(clean)
    return urls

def extract_next_page_url(html, current_url):
    soup = BeautifulSoup(html, 'html.parser')
    next_link = soup.select_one('a[aria-label="Next page"], a[aria-label="Next"], a.pagination__next') or soup.find('a', string=lambda text: bool(text and text.strip().lower() == 'next'))
    return uparse.urljoin(current_url, next_link.get('href')) if next_link and next_link.get('href') else None

def extract_oxylabs_item_links(url, max_pages=10, increment_usage_callback=None):
    parsed = uparse.urlparse(url)
    qs = uparse.parse_qs(parsed.query)
    qs['_ipg'] = ['240']
    current_url = uparse.urlunparse(parsed._replace(query=uparse.urlencode(qs, doseq=True)))
    
    seen_pages, seen_items, item_links = set(), set(), []
    
    for page in range(1, max_pages + 1):
        if current_url in seen_pages: break
        seen_pages.add(current_url)
        print(f"⚙️ Oxylabs: Extrayendo links página {page}/{max_pages}: {current_url}")
        html = fetch_oxylabs_html(current_url, increment_usage_callback)
        if not html: break
        
        for item_url in extract_item_links_from_search_html(html):
            if item_url not in seen_items:
                seen_items.add(item_url)
                item_links.append(item_url)
                
        next_url = extract_next_page_url(html, current_url)
        if not next_url: break
        parsed = uparse.urlparse(next_url)
        qs = uparse.parse_qs(parsed.query)
        qs['_ipg'] = ['240']
        current_url = uparse.urlunparse(parsed._replace(query=uparse.urlencode(qs, doseq=True)))
        
    return item_links

def scrape_url(url, increment_usage_callback=None, existing_ids=None):
    try:
        if is_item_url(url):
            item_id = extract_item_id(url)
            if existing_ids and item_id in existing_ids:
                print(f"   ⏭️ Ya en DB, saltando: {item_id}")
                return empty_result()
            print(f"⚙️ Oxylabs: Scrapeando item: {url}")
            html = fetch_oxylabs_html(url, increment_usage_callback)
            return parse_item_html(html, url) if html else empty_result()

        if is_search_or_store_url(url):
            item_links = extract_oxylabs_item_links(url, increment_usage_callback=increment_usage_callback)
            if not item_links:
                print("⚠️ No se encontraron items en la tienda/búsqueda")
                return empty_result()

            resultados = []
            for i, item_url in enumerate(item_links, 1):
                item_id = extract_item_id(item_url)
                if existing_ids and item_id in existing_ids:
                    print(f"   ⏭️ Ya en DB, saltando: {item_id}")
                    continue
                print(f"🔍 Scrapeando item {i}/{len(item_links)}: {item_url}")
                html = fetch_oxylabs_html(item_url, increment_usage_callback)
                if html:
                    df = parse_item_html(html, item_url)
                    if not df.empty:
                        resultados.append(df)
                        print(f"   ✔ OK")
                    else:
                        print(f"   ⚠️ Sin datos")
                time.sleep(REQUEST_DELAY)

            return pd.concat(resultados, ignore_index=True) if resultados else empty_result()

        print(f"⚠️ URL de eBay no reconocida: {url}")
        return empty_result()

    except Exception as e:
        print(f"❌ Error en scrape_url: {e}")
        return empty_result()
