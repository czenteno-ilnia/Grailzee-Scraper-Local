from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
import pandas as pd
import requests

from chrono24_fetch import get_soup_with_browser as _get_soup_with_browser
from chrono24_fetch import get_soup_with_requests as _get_soup_with_requests

COLUMNS = [
    "Stock",
    "URL",
    "Make",
    "Model",
    "Reference Number",
    "Year",
    "Box",
    "Papers",
    "Original Price",
    "Customized",
    "Seller",
]

BASE_URL = "https://www.chrono24.com"
MAX_VENDOR_PAGES = 20
MAX_LISTINGS = 300
ProgressCallback = Callable[[str], None]


def _strip_tracking(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _get_soup(url: str) -> BeautifulSoup:
    soup = _get_soup_with_requests(url)
    if soup is not None:
        return soup
    return _get_soup_with_browser(url)


def _is_listing_url(url: str) -> bool:
    return "--id" in url and urlsplit(url).path.endswith(".htm")


def _extract_listing_urls(soup: BeautifulSoup, page_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        candidate = _strip_tracking(urljoin(page_url, href))
        if _is_listing_url(candidate) and candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)

    return urls


def _find_next_page_url(soup: BeautifulSoup, page_url: str) -> str | None:
    next_link = soup.find("a", attrs={"rel": re.compile("next", re.I)}, href=True)
    if next_link is None:
        next_link = soup.find("a", attrs={"aria-label": re.compile("next", re.I)}, href=True)
    if next_link is None:
        next_link = soup.find("a", string=re.compile(r"^\s*next\s*$", re.I), href=True)

    if next_link is None:
        return None

    return urljoin(page_url, str(next_link["href"]))


def _build_spec_map(soup: BeautifulSoup) -> dict[str, str]:
    specs: dict[str, str] = {}
    for row in soup.find_all("tr"):
        label_tag = row.find("th") or row.find("strong")
        value_tag = row.find("td")
        if label_tag is None or value_tag is None:
            continue

        label = label_tag.get_text(" ", strip=True).rstrip(":")
        value = value_tag.get_text(" ", strip=True).split("The item shows")[0].strip()
        if label and value:
            specs.setdefault(label, value)
    return specs


def _extract_price(soup: BeautifulSoup, specs: dict[str, str]) -> str:
    price_tag = soup.select_one(".detail-page-price .js-price-shipping-country, [data-testid='price']")
    if price_tag is not None:
        return price_tag.get_text(" ", strip=True)
    return specs.get("Price", "Missing")


def _extract_box_papers(specs: dict[str, str]) -> tuple[str, str]:
    scope = specs.get("Scope of delivery", "").lower()
    if not scope:
        return "Missing", "Missing"

    box = "No" if re.search(r"no\s+(original\s+)?box", scope) else "Yes" if "box" in scope else "Missing"
    papers = "No" if re.search(r"no\s+(original\s+)?paper", scope) else "Yes" if "paper" in scope else "Missing"
    return box, papers


def collect_listing_urls(
    search_url: str,
    max_pages: int = MAX_VENDOR_PAGES,
    progress_callback: ProgressCallback | None = None,
) -> list[str]:
    max_listings = int(os.environ.get("CHRONO24_MAX_LISTINGS", str(MAX_LISTINGS)))
    urls: list[str] = []
    seen: set[str] = set()
    page_url: str | None = search_url

    for page_number in range(1, max_pages + 1):
        if page_url is None:
            break

        if progress_callback is not None:
            progress_callback(f"   Chrono24: leyendo pagina {page_number}: {page_url}")
        soup = _get_soup(page_url)
        for listing_url in _extract_listing_urls(soup, page_url):
            if listing_url not in seen:
                seen.add(listing_url)
                urls.append(listing_url)
                if progress_callback is not None and len(urls) % 10 == 0:
                    progress_callback(f"   Chrono24: {len(urls)} listings encontrados...")
                if len(urls) >= max_listings:
                    if progress_callback is not None:
                        progress_callback(f"   Chrono24: limite de {max_listings} listings alcanzado")
                    return urls

        next_url = _find_next_page_url(soup, page_url)
        page_url = next_url if next_url not in seen else None

    if progress_callback is not None:
        progress_callback(f"   Chrono24: {len(urls)} listings encontrados")
    return urls


def _parse_chrono24_detail(soup: BeautifulSoup, url: str) -> dict[str, str]:
    specs = _build_spec_map(soup)
    box, papers = _extract_box_papers(specs)

    h1 = soup.find("h1")
    seller = soup.select_one(".js-link-merchant-name")
    return {
        "url": url,
        "Title": h1.get_text(" ", strip=True) if h1 else "Missing",
        "Listing code": specs.get("Listing code", specs.get("Listing ID", "Missing")),
        "Brand": specs.get("Brand", "Missing"),
        "Model": specs.get("Model", "Missing"),
        "Reference number": specs.get("Reference number", "Missing"),
        "Year of production": specs.get("Year of production", "Missing"),
        "Price": _extract_price(soup, specs),
        "With box": box,
        "With papers": papers,
        "Seller": seller.get_text(" ", strip=True) if seller else "Missing",
    }


def _row_from_info(info: dict[str, str]) -> dict[str, str]:
    return {
        "Stock": info.get("Listing code", "Missing"),
        "URL": info.get("url", "Missing"),
        "Make": info.get("Brand", "Missing"),
        "Model": info.get("Model", "Missing"),
        "Reference Number": info.get("Reference number", "Missing"),
        "Year": info.get("Year of production", "Missing"),
        "Box": info.get("With box", "Missing"),
        "Papers": info.get("With papers", "Missing"),
        "Original Price": info.get("Price", "Missing"),
        "Customized": "Missing",
        "Seller": info.get("Seller", "Missing"),
    }


def _expand_input_url(url: str, progress_callback: ProgressCallback | None = None) -> list[str]:
    clean_url = _strip_tracking(url)
    if _is_listing_url(clean_url):
        return [clean_url]
    return collect_listing_urls(url, progress_callback=progress_callback)


def scrape_multiple(
    urls: list[str],
    existing_ids: set[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    existing = set() if existing_ids is None else existing_ids

    for url in urls:
        listing_urls = _expand_input_url(url, progress_callback=progress_callback)
        total = len(listing_urls)
        if progress_callback is not None:
            progress_callback(f"   Chrono24: procesando {total} listings")
        skipped = 0
        for index, listing_url in enumerate(listing_urls, 1):
            if listing_url in seen:
                continue
            seen.add(listing_url)
            if listing_url in existing or _strip_tracking(listing_url) in existing:
                skipped += 1
                if progress_callback is not None and skipped % 10 == 0:
                    progress_callback(f"   Chrono24: {skipped} ya existentes omitidos...")
                continue
            try:
                if progress_callback is not None:
                    progress_callback(f"   Chrono24: scrapeando item {index}/{total}: {listing_url}")
                soup = _get_soup_with_requests(listing_url)
                if soup is None:
                    if progress_callback is not None:
                        progress_callback("   Chrono24: abriendo Chrome/Selenium para detalles")
                    soup = _get_soup_with_browser(listing_url)
                info = _parse_chrono24_detail(soup, listing_url)
                rows.append(_row_from_info(info))
            except (requests.RequestException, RuntimeError, OSError, ImportError) as exc:
                error_message = f"ERROR scraping {listing_url}: {exc}"
                print(error_message)
                if progress_callback is not None:
                    progress_callback(f"   Chrono24: {error_message}")
                rows.append(_row_from_info({"url": listing_url}))
        if progress_callback is not None and skipped:
            progress_callback(f"   Chrono24: {skipped} listings ya estaban en el CSV")

    return pd.DataFrame(rows, columns=COLUMNS)


def _write_report(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    target_urls = sys.argv[1:] or ["https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true"]
    report_path = Path("reportes") / "reporte_scraper.csv"
    result = scrape_multiple(target_urls)
    _write_report(result, report_path)
    print(f"Saved {len(result)} rows to {report_path}")
