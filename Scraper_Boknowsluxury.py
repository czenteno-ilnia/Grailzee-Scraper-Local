import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

def extract_collapsible_data(soup):
    data = {}

    container = soup.select_one("div.collapsible__content")
    if not container:
        return data

    text = container.get_text("\n", strip=True)

    # ---------- REFERENCE ----------
    m = re.search(r"Reference:\s*([A-Z0-9\s\-]+)", text, re.I)
    if m:
        data["Reference Number"] = m.group(1).strip()

    # ---------- YEAR ----------
    m = re.search(r"\b(19|20)\d{2}\b", text)
    if m:
        data["Year"] = m.group(0)

    # ---------- MSRP ----------
    m = re.search(r"MSRP:\s*\$([\d,]+)", text)
    if m:
        data["MSRP"] = float(m.group(1).replace(",", ""))

    # ---------- BRAND ----------
    m = re.search(r"Brand:\s*(.+)", text)
    if m:
        data["Make"] = m.group(1).strip()

    # ---------- MODEL ----------
    m = re.search(r"Model:\s*(.+)", text)
    if m:
        data["Model"] = m.group(1).strip()

    # ---------- CONDITION ----------
    m = re.search(r"Condition:\s*(.+)", text)
    if m:
        data["Condition"] = m.group(1).strip()

    # ---------- BOX & PAPERS ----------
    included = re.search(r"(Box and Papers|box and papers|original box and papers)", text, re.I)
    if included:
        data["Box"] = "Yes"
        data["Papers"] = "Yes"

    # ---------- STOCK ----------
    m = re.search(r"Stock ID:\s*([A-Z0-9\-]+)", text, re.I)
    if m:
        data["Stock"] = m.group(1)

    return data


def Scraper_Boknowsluxury(url_Boknowsluxury):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9"
    }

    response = requests.get(url_Boknowsluxury, headers=headers)
    if response.status_code != 200:
        print(f"Error al acceder: {response.status_code}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

    soup = BeautifulSoup(response.text, "html.parser")

    # ============ VARIABLES BASE =============
    url = url_Boknowsluxury
    stock = "Missing information"
    make = "Missing information"
    model = "Missing information"
    reference_Number = "Missing information"
    year = "Missing information"
    box = "Missing information"
    papers = "Missing information"
    original_price = "Missing information"

    # ============ SPECIFICATIONS TABLE ============
    collapsible = extract_collapsible_data(soup)

    # Fallbacks desde collapsible
    stock = collapsible.get("Stock", stock)
    make = collapsible.get("Make", make)
    model = collapsible.get("Model", model)
    reference_Number = collapsible.get("Reference Number", reference_Number)
    year = collapsible.get("Year", year)
    box = collapsible.get("Box", box)
    papers = collapsible.get("Papers", papers)



    # ============ PRECIO (Boknowsluxury / Shopify) =============
    price_tag = (
        soup.select_one(".price__on-sale .exception")
        or soup.select_one(".price__regular span:not(.visually-hidden)")
    )

    if price_tag:
        price_text = price_tag.get_text(strip=True)
        # Limpieza básica: "$6,482.47 USD" → 6482.47
        price_clean = re.sub(r"[^\d.]", "", price_text)
        try:
            original_price = float(price_clean)
        except:
            original_price = price_text
    else:
        original_price = "Missing information"

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
        return Scraper_Boknowsluxury(url)
    except Exception as e:
        print(f"❌ Error en scrape_url (Boknowsluxury): {e}")
        return pd.DataFrame(columns=[
            "Stock","URL","Make","Model","Reference Number","Year","Box","Papers","Original Price"
        ])

if __name__ == "__main__":
    test_url = "https://boknowsluxury.com/products/hublot-spirit-of-big-bang-642-ci-0191-rx-ecu23-ceramic-carbon-beige-camo-42mm"
    print(Scraper_Boknowsluxury(test_url))
