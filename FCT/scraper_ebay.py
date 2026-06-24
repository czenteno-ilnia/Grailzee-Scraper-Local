from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import pandas as pd
import re
import chromedriver_autoinstaller

chromedriver_autoinstaller.install()

# Normaliza etiquetas
def normalize_label(label):
    s = re.sub(r'\s+', ' ', label.strip().lower())
    if s.endswith(':'):
        s = s[:-1].strip()
    mapping = {
        "estado": "Status", "status": "Status", "estado del articulo": "Status", "condition": "Status",
        "make": "Make", "marca": "Make", "brand": "Make",
        "model": "Model", "modelo": "Model",
        "reference number": "Reference Number", "reference": "Reference Number", "reference no.": "Reference Number",
        "número de referencia": "Reference Number", "numero de referencia": "Reference Number",
        "year": "Year", "año": "Year", "ano": "Year",
        "box": "Box", "caja": "Box", "with original box": "Box", "with original box/packaging": "Box",
        "papers": "Papers", "papeles": "Papers", "documentación": "Papers", "with papers": "Papers",
    }
    return mapping.get(s, None)

def detect_box_papers(specs):
    box, papers = "No", "No"
    for label, value in specs.items():
        v = value.strip().lower()
        l = label.lower()
        if any(k in l or k in v for k in ["box", "caja", "pack", "embalaje"]) and "no" not in v:
            box = "Yes"
        if any(k in l or k in v for k in ["papers", "papeles", "documentación", "documentation"]) and "no" not in v:
            papers = "Yes"
    return box, papers

def scrape_url(url):
    opts = Options()
    opts.add_argument("--disable-gpu")
    opts.add_argument("--headless=new")

    driver = webdriver.Chrome(options=opts)
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.x-bin-price'))
        )
    except TimeoutException:
        print(f"Advertencia: no se encontró el precio en {url}")

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    specs = {dt.get_text(strip=True): dd.get_text(strip=True)
             for dt, dd in zip(soup.select("dt.ux-labels-values__labels"),
                               soup.select("dd.ux-labels-values__values"))}

    box_value, papers_value = detect_box_papers(specs)

    canonical = {
        "Make": next((v for k, v in specs.items() if normalize_label(k) == "Make"), "Missing information"),
        "Model": next((v for k, v in specs.items() if normalize_label(k) == "Model"), "Missing information"),
        "Reference Number": next((v for k, v in specs.items() if normalize_label(k) == "Reference Number"), "Missing information"),
        "Year": next((v for k, v in specs.items() if normalize_label(k) == "Year" and not re.search(r'\b(mm|cm|inch)\b', v.lower())), "Missing information"),
        "Box": box_value,
        "Papers": papers_value
    }

    price_element = soup.select_one('div[data-testid="x-price-primary"] span')
    if price_element:
        raw_price = price_element.get_text(strip=True)
        cleaned = raw_price.replace("\u00A0", " ").strip("() ")
        match = re.search(r"\$\s?[\d\s.,]+", cleaned)
        clean_price = match.group(0).replace(" ", "") if match else "Missing Information"
    else:
        clean_price = "Missing Information"

    item = {
        "Stock": soup.select_one('div.ux-layout-section__textual-display--itemId span.ux-textspans--BOLD').get_text(strip=True)
        if soup.select_one('div.ux-layout-section__textual-display--itemId span.ux-textspans--BOLD') else "Missing information",
        "URL": url,
        "Original Price": clean_price
    }
    item.update(canonical)

    columns_order = ["Stock", "URL", "Make", "Model", "Reference Number", "Year", "Box", "Papers", "Original Price"]
    return pd.DataFrame([item])[columns_order]

def scrape_multiple(urls):
    dfs = [scrape_url(url) for url in urls]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
