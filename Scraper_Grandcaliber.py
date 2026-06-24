import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

def extract_product_text_attributes(soup):
    """
    Extrae Brand, Model, Reference, Year, Stock, Box, Papers
    desde el bloque product__text
    """
    data = {}

    container = soup.select_one("div.product__text")
    if not container:
        return data

    text = container.get_text("\n", strip=True)

    for line in text.split("\n"):
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()

    return data


def extract_price_grandcaliber(soup):
    price_span = soup.select_one("span.price__regular")
    if not price_span:
        return "Missing information"
    return price_span.get_text(strip=True)


def Scraper_Grandcaliber(url_Grandcaliber):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9"
    }

    response = requests.get(url_Grandcaliber, headers=headers)
    if response.status_code != 200:
        print(f"Error al acceder: {response.status_code}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number",
            "Year","Box","Papers","Original Price"
        ])

    soup = BeautifulSoup(response.text, "html.parser")

    # ============ DEFAULTS ============
    stock = make = model = reference_Number = year = box = papers = "Missing information"

    # ============ EXTRAER TEXTO ============
    attrs = extract_product_text_attributes(soup)

    make = attrs.get("Brand", make)
    model = attrs.get("Model", model)
    reference_Number = attrs.get("Reference", reference_Number)
    year = attrs.get("Date", year)
    stock = attrs.get("Stock ID", stock)

    included = attrs.get("Included Items", "")
    if "box" in included.lower():
        box = "Yes"
    if "papers" in included.lower():
        papers = "Yes"

    # ============ PRECIO ============
    original_price = extract_price_grandcaliber(soup)

    # ============ FORMATO FINAL ============
    data = {
        "Stock": stock,
        "URL": url_Grandcaliber,
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
        return Scraper_Grandcaliber(url)
    except Exception as e:
        print(f"❌ Error en scrape_url (Grandcaliber): {e}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

if __name__ == "__main__":
    test_url = "https://grandcaliber.com/products/omega-seamaster-diver-300-m-210-92-44-20-01-001-dallas-omega-watches"
    print(Scraper_Grandcaliber(test_url))
