import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

def extract_product_description_attributes(soup):
    """
    Extrae Manufacturer, Model Name, Model Number, Year, Box/Papers, etc.
    desde product__description (<li> o <p>)
    """
    data = {}

    container = soup.select_one("div.product__description")
    if not container:
        return data

    for li in container.select("li, p"):
        text = li.get_text(" ", strip=True)

        if ":" not in text:
            continue

        label, value = text.split(":", 1)
        label = label.strip().lower()
        value = value.strip()

        if "manufacturer" in label:
            data["Make"] = value

        elif "model name" in label:
            data["Model"] = value

        elif "model number" in label:
            data["Reference Number"] = value

        elif "box/papers" in label:
            data["Box"] = "Yes"
            data["Papers"] = "Yes"

            year = extract_year_from_text(value)
            if year:
                data["Year"] = year

        elif "condition" in label:
            data["Condition"] = value

    return data


def extract_custom_settings(soup):
    """
    Extrae datos desde el bloque customSettings
    """
    data = {}

    container = soup.select_one("div.customSettings")
    if not container:
        return data

    for li in container.select("li"):
        title = li.select_one(".title")
        value = title.find_next_sibling("span") if title else None

        if not title or not value:
            continue

        label = title.get_text(strip=True).lower()
        val = value.get_text(strip=True)

        if label == "brand":
            data["Make"] = val
        elif label == "simple code":
            m = re.search(r"\b\d{4,6}[A-Z]{0,3}\b", val)
            if m:
                data["Reference Number"] = m.group(0)

        elif label == "box & papers":
            data["Box"] = val
            data["Papers"] = val
        elif label == "gender":
            data["Gender"] = val
        elif label == "movement":
            data["Movement"] = val
        elif label == "size":
            data["Case Size"] = val

    return data

def extract_reference_from_product_text(soup):
    """
    Extrae Reference Number desde <p class="product__text inline-richtext">
    Ejemplo: 'Model: 126331 slgrj' → 126331
    """
    p = soup.select_one("p.product__text.inline-richtext")
    if not p:
        return None

    text = p.get_text(strip=True)

    # Busca referencia tipo Rolex
    m = re.search(r"\b\d{4,6}[A-Z]{0,3}\b", text)
    if m:
        return m.group(0)

    return None

def normalize_reference_number(ref):
    """
    Deja el Reference Number SOLO en números (4 a 6 dígitos)
    """
    if not ref or ref == "Missing information":
        return ref

    m = re.search(r"\b\d{4,6}\b", ref)
    if m:
        return m.group(0)

    return "Missing information"


def extract_year_from_text(text):
    """
    Extrae el año desde texto:
    - Soporta 'dated 2019'
    - Soporta 'dated 5/2025' o '05/2025'
    """
    if not text:
        return None

    # Caso 1: mes/año → 5/2025
    m = re.search(r"\b\d{1,2}/((19|20)\d{2})\b", text)
    if m:
        return m.group(1)

    # Caso 2: solo año → 2019
    m = re.search(r"\b(19|20)\d{2}\b", text)
    if m:
        return m.group(0)

    return None


def extract_effective_price_shopify(soup):
    """
    Devuelve un solo precio desde Shopify:
    - Prioriza precio de oferta (.price-item--sale)
    - Si no existe, usa precio regular
    """
    # Precio en oferta
    sale = soup.select_one(".price__container .price-item--sale")
    if sale:
        return sale.get_text(strip=True)

    # Precio regular
    regular = soup.select_one(".price__container .price-item--regular")
    if regular:
        return regular.get_text(strip=True)

    return "Missing information"


def Scraper_Timepieceperfection(url_Timepieceperfection):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9"
    }

    response = requests.get(url_Timepieceperfection, headers=headers)
    if response.status_code != 200:
        print(f"Error al acceder: {response.status_code}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

    soup = BeautifulSoup(response.text, "html.parser")

    # ============ VARIABLES BASE =============
    url = url_Timepieceperfection
    stock = "Missing information"
    make = "Missing information"
    model = "Missing information"
    reference_Number = "Missing information"
    year = "Missing information"
    box = "Missing information"
    papers = "Missing information"
    original_price = "Missing information"

    # ============ EXTRAER CAMPOS DIRECTOS DESDE EL DIV =============
    desc_data = extract_product_description_attributes(soup)
    custom_data = extract_custom_settings(soup)

    # Prioridad: descripción → customSettings
    make = desc_data.get("Make") or custom_data.get("Make", make)
    model = desc_data.get("Model", model)
    # Reference Number - orden de prioridad correcto
    reference_Number = (
        desc_data.get("Reference Number")
        or custom_data.get("Reference Number")
        or extract_reference_from_product_text(soup)
        or reference_Number
    )
    reference_Number = normalize_reference_number(reference_Number)

    box = desc_data.get("Box") or custom_data.get("Box", box)
    papers = desc_data.get("Papers") or custom_data.get("Papers", papers)
    year = desc_data.get("Year", year)

    # ============ PRECIO (WooCommerce) =============
    original_price = extract_effective_price_shopify(soup)

    # ============ FORMATO FINAL =============
    data = {
        "Stock": stock,
        "URL": url,
        "Make": make,
        "Model": model,
        "Reference Number": reference_Number,
        "Year": year,
        "Box": box,
        "Papers": papers,
        "Original Price": original_price
    }

    return pd.DataFrame([data])[[
        "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
    ]]

# ============================================
#     ADAPTADOR PARA FORMATO UNIVERSAL
# ============================================

def scrape_url(url):
    try:
        return Scraper_Timepieceperfection(url)
    except Exception as e:
        print(f"❌ Error en scrape_url (Timepieceperfection): {e}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

if __name__ == "__main__":
    test_url = "https://timepieceperfection.com/products/rolex-datejust-41mm-steel-rose-gold-wimbledon"
    print(Scraper_Timepieceperfection(test_url))
