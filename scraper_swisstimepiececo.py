import requests
from bs4 import BeautifulSoup
import re
import pandas as pd


def extract_reference_number(title, page_text, make_candidates=None):
    if make_candidates is None:
        make_candidates = []

    m = re.search(r"\( *ref\.? *[:#]?\s*([A-Za-z0-9\-]{3,20}) *\)", title, re.I)
    if m: return m.group(1).strip()

    m = re.search(r"\bref\.? *[:#]?\s*([A-Za-z0-9\-]{3,20})\b", title, re.I)
    if m: return m.group(1).strip()

    m = re.search(r"\bref\.? *[:#]?\s*([A-Za-z0-9\-]{3,20})\b", page_text, re.I)
    if m: return m.group(1).strip()

    tokens = re.split(r"[\s–—\-]+", title.strip())
    if tokens:
        last = tokens[-1].strip()
        if last.lower() not in [m.lower() for m in make_candidates]:
            if re.fullmatch(r"[A-Za-z0-9\-]{3,12}", last):
                blacklist = {"new", "black", "white", "silver", "gold",
                             "steel", "bronze", "blue", "green", "red"}
                if last.lower() not in blacklist:
                    return last

    m = re.search(r"\(?.{0,10}ref\.? *[:#]?\s*([A-Za-z0-9\-]{3,20})\)?", page_text, re.I)
    if m: return m.group(1).strip()

    return ""


# =====================================================
#    SCRAPER SWISSTIMEPIECECO EN FORMATO eBay
# =====================================================
def Scraper_Swisstimepiececo(url_Swisstimepiececo):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9"
    }

    response = requests.get(url_Swisstimepiececo, headers=headers)
    if response.status_code != 200:
        print(f"Error al acceder: {response.status_code}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

    soup = BeautifulSoup(response.text, "html.parser")

    # INICIALIZAR
    stock = "Missing information"
    url = url_Swisstimepiececo
    make = "Missing information"
    model = "Missing information"
    reference_Number = "Missing information"
    year = "Missing information"
    box = "Unknown"
    papers = "Unknown"
    original_price = "Missing Information"

    # ===== TÍTULO =====
    title_tag = soup.select_one("div.product__title h1")
    if title_tag:
        title = title_tag.get_text(strip=True)

        marcas = [
            "Breitling", "Rolex", "Omega", "Tudor", "Cartier", "Tag",
            "Hublot", "Patek", "Audemars", "IWC", "Longines", "Panerai"
        ]

        palabras = title.split()
        primera = palabras[1] if palabras[0].upper() == "NEW" else palabras[0]

        if primera.capitalize() in marcas:
            make = primera.capitalize()

        page_text = soup.get_text(" ", strip=True)
        reference_Number = extract_reference_number(title, page_text, marcas)
        model = title.replace("NEW", "")
        if make != "Missing information": model = model.replace(make, "")
        if reference_Number != "Missing information": model = model.replace(reference_Number, "")
        model = re.sub(r"\(.*?\)", "", model).strip()

    # ===== PRECIO =====
    price_tag = soup.select_one(".price-item--sale, .price-item--regular")
    if price_tag:
        original_price = price_tag.get_text(strip=True)

    # ===== AÑO =====
    description_text = soup.get_text(" ", strip=True)
    year_match = re.search(r"\b(19|20)\d{2}\b", description_text)
    if year_match:
        year = year_match.group(0)

    # ===== BOX / PAPERS =====
    box = "Yes" if re.search(r"\bbox\b|\bcomplete set\b", description_text, re.I) else "No"
    papers = "Yes" if re.search(r"\bpaper\b|\bwarranty\b|\bcard\b", description_text, re.I) else "No"

    # =====================================================
    #     FORMATO EXACTO DE SALIDA (DATAFRAME COMO eBAY)
    # =====================================================
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
#     MainApp espera: scrape_url(url)
# ============================================

def scrape_url(url):
    """
    Función estándar igual que scraper_ebay.
    Simplemente llama a Scraper_Swisstimepiececo y devuelve el DataFrame.
    """
    try:
        return Scraper_Swisstimepiececo(url)
    except Exception as e:
        print(f"❌ Error en scrape_url (Swiss): {e}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

if __name__ == "__main__":
    test_url = "https://swisstimepiececo.com/products/new-breitling-endurance-pro-38-white-x83310"
    print(Scraper_Swisstimepiececo(test_url))
