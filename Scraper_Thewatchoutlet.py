import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

def extract_woocommerce_attributes(soup):
    """
    Extrae los atributos de la pestaña 'Additional Information'
    y los devuelve como diccionario.
    """
    attributes = {}

    table = soup.select_one(
        "div#tab-additional_information table.woocommerce-product-attributes"
    )

    if not table:
        return attributes

    for row in table.select("tr"):
        th = row.select_one("th")
        td = row.select_one("td")

        if not th or not td:
            continue

        label = th.get_text(strip=True)

        values = [a.get_text(strip=True) for a in td.select("a")]
        value = ", ".join(values) if values else td.get_text(strip=True)

        attributes[label] = value

    return attributes

def extract_effective_price_woocommerce(soup):
    """
    Devuelve un solo precio:
    - Si hay precio rebajado (<ins>), usa ese
    - Si no, usa el precio original
    """
    price = soup.select_one("p.price")
    if not price:
        return "Missing information"

    ins_price = price.select_one("ins bdi")
    if ins_price:
        return ins_price.get_text(strip=True)

    # Sin descuento → precio normal
    bdi = price.select_one("bdi")
    if bdi:
        return bdi.get_text(strip=True)

    return "Missing information"

def extract_reference_number_woocommerce(soup, url):
    """
    Extrae el Reference Number desde múltiples fuentes,
    evitando marcas y falsos positivos.
    """

    # -------- 1. TABLA WOOCOMMERCE --------
    attributes = extract_woocommerce_attributes(soup)
    for key in ["Reference Number", "Reference #", "Ref", "Model Number"]:
        val = attributes.get(key)
        if val and any(c.isdigit() for c in val):
            return val.strip()

    # -------- 2. TABLA item-table --------
    for row in soup.select("table.item-table tr"):
        cells = row.find_all("td")
        if len(cells) != 2:
            continue

        label = cells[0].get_text(strip=True).lower()
        value = cells[1].get_text(strip=True)

        if label in {"reference #", "reference", "ref", "ref."}:
            if any(c.isdigit() for c in value):
                return value.strip()

    # Regex robusto (OBLIGA números)
    ref_regex = re.compile(
        r"\b(?=[A-Z0-9\-]{4,20}\b)(?=.*\d)[A-Z]+[A-Z0-9\-]*\d[A-Z0-9\-]*\b",
        re.I
    )

    BLACKLIST = {
        "BREMONT", "ROLEX", "OMEGA", "WATCH",
        "AUTOMATIC", "SWISS", "MEN", "MENS",
        "DIAL", "STEEL"
    }

    def valid_ref(candidate):
        return candidate.upper() not in BLACKLIST

    # -------- 3. TÍTULO --------
    title = soup.select_one("h1.product_title")
    if title:
        for m in ref_regex.finditer(title.get_text()):
            ref = m.group().upper()
            if valid_ref(ref):
                return ref

    # -------- 4. URL --------
    slug = url.rstrip("/").split("/")[-1].upper()
    for m in ref_regex.finditer(slug):
        ref = m.group()
        if valid_ref(ref):
            return ref

    # -------- 5. TEXTO COMPLETO --------
    text = soup.get_text(" ", strip=True)
    for m in ref_regex.finditer(text):
        ref = m.group().upper()
        if valid_ref(ref):
            return ref

    return "Missing information"


    # -------- 3. TÍTULO --------
    title = soup.select_one("h1.product_title")
    if title:
        match = ref_regex.search(title.get_text())
        if match:
            return match.group().upper()

    # -------- 4. URL --------
    slug = url.rstrip("/").split("/")[-1].upper()
    match = ref_regex.search(slug)
    if match:
        return match.group()

    # -------- 5. TEXTO COMPLETO --------
    text = soup.get_text(" ", strip=True)
    match = ref_regex.search(text)
    if match:
        return match.group().upper()

    return "Missing information"


def Scraper_Thewatchoutlet(url_Thewatchoutlet):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9"
    }

    response = requests.get(url_Thewatchoutlet, headers=headers)
    if response.status_code != 200:
        print(f"Error al acceder: {response.status_code}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

    soup = BeautifulSoup(response.text, "html.parser")

    # ============ VARIABLES BASE =============
    url = url_Thewatchoutlet
    stock = "Missing information"
    make = "Missing information"
    model = "Missing information"
    reference_Number = "Missing information"
    year = "Missing information"
    box = "Missing information"
    papers = "Missing information"
    original_price = "Missing information"

    # ============ EXTRAER CAMPOS DIRECTOS DESDE EL DIV =============
    attributes = extract_woocommerce_attributes(soup)

    make = attributes.get("Brand", "Missing information")
    model = attributes.get("Model", "Missing information")

    # Estos pueden no existir en WooCommerce
    reference_Number = extract_reference_number_woocommerce(soup, url)
    year = attributes.get("Year of Production", "Unknown")

    #---Box & Paper
    for span in soup.select("span.awl-inner-text"):
        text = span.text.strip()

        if text.startswith("Box:"):
            box = text.replace("Box:", "").strip()

        elif text.startswith("Papers:"):
            papers = text.replace("Papers:", "").strip()


    # ============ PRECIO (WooCommerce) =============
    original_price = extract_effective_price_woocommerce(soup)



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
        return Scraper_Thewatchoutlet(url)
    except Exception as e:
        print(f"❌ Error en scrape_url (Thewatchoutlet): {e}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

if __name__ == "__main__":
    test_url = "https://thewatchoutlet.com/product/bovet-sportster-chronograph-18k-rose-gold-46mm-automatic-mens-watch-sp0479/"
    print(Scraper_Thewatchoutlet(test_url))
