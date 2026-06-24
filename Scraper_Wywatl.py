import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

def extraer_campo(soup, campo):
    div = soup.select_one("div.product__description.rte.quick-add-hidden")
    if not div:
        return None
    p = div.find("p", string=lambda text: text and text.strip().startswith(campo + ":"))
    if p:
        return p.get_text(strip=True).split(":", 1)[1].strip()
    return None

#    SCRAPER WY WAT L EN FORMATO eBay
# =====================================================
def Scraper_Wywatl(url_Wywatl):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9"
    }

    response = requests.get(url_Wywatl, headers=headers)
    if response.status_code != 200:
        print(f"Error al acceder: {response.status_code}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

    soup = BeautifulSoup(response.text, "html.parser")

    # ============ VARIABLES BASE =============
    url = url_Wywatl
    stock = "Missing information"

    # ============ EXTRAER CAMPOS DIRECTOS DESDE EL DIV =============
    make = extraer_campo(soup, "Brand") or "Missing information"
    model = extraer_campo(soup, "Model") or "Missing information"
    reference_Number = extraer_campo(soup, "Reference Number") or "Missing information"
    year = extraer_campo(soup, "Year of Production") or "Unknown"
    box = extraer_campo(soup, "Box") or "Unknown"
    papers = extraer_campo(soup, "Papers/Warranty Card") or "Unknown"

    # ============ PRECIO =============
    price_tag = soup.select_one("span.price-item.price-item--regular")
    original_price = price_tag.get_text(strip=True) if price_tag else "Missing Information"

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
        return Scraper_Wywatl(url)
    except Exception as e:
        print(f"❌ Error en scrape_url (Wywatl): {e}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

if __name__ == "__main__":
    test_url = "https://www.wywatl.com/products/cartier-tank-americaine-26x45mm-1741-white-guilloche-dial?variant=50609178935581"
    print(Scraper_Wywatl(test_url))
