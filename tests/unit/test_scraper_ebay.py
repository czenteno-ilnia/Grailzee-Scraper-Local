from __future__ import annotations

import pandas as pd
import pytest

import scraper_ebay
from scraper_ebay import (
    COLUMNS,
    extract_item_id,
    is_item_url,
    is_search_or_store_url,
)


EXPECTED_COLUMNS = [
    "Stock",
    "URL",
    "Make",
    "Model",
    "Reference Number",
    "Year",
    "Box",
    "Papers",
    "Original Price",
]


def assert_exact_columns(df: pd.DataFrame) -> None:
    assert list(df.columns) == EXPECTED_COLUMNS


def assert_empty_exact_columns(df: pd.DataFrame) -> None:
    assert_exact_columns(df)
    assert df.empty


# =========================
# extract_item_id
# =========================
@pytest.mark.unit
def test_extract_item_id_when_url_contains_item_path() -> None:
    url = "https://www.ebay.com/itm/316846911220?hash=abc"
    assert extract_item_id(url) == "316846911220"


@pytest.mark.unit
def test_extract_item_id_when_url_is_not_item_url() -> None:
    assert extract_item_id("https://www.ebay.com/sch/i.html?_nkw=rolex") is None


# =========================
# is_item_url / is_search_or_store_url
# =========================
@pytest.mark.unit
def test_is_item_url_recognizes_item_pages() -> None:
    assert is_item_url("https://www.ebay.com/itm/186641306493") is True
    assert is_item_url("https://www.ebay.com/itm/123?hash=abc") is True


@pytest.mark.unit
def test_is_item_url_rejects_non_item_pages() -> None:
    assert is_item_url("https://www.ebay.com/sch/i.html?_nkw=rolex") is False
    assert is_item_url("https://www.ebay.com/str/someshop") is False


@pytest.mark.unit
def test_is_search_or_store_url_recognizes_store_and_search() -> None:
    assert is_search_or_store_url(
        "https://www.ebay.com/sch/i.html?_ssn=chronodynamix&store_name=markswatchesusa"
    ) is True
    assert is_search_or_store_url("https://www.ebay.com/str/someshop") is True
    assert is_search_or_store_url("https://www.ebay.com/sch/i.html?_nkw=rolex") is True


@pytest.mark.unit
def test_is_search_or_store_url_rejects_item_only_urls() -> None:
    assert is_search_or_store_url("https://www.ebay.com/itm/123456") is False


# =========================
# COLUMNS
# =========================
@pytest.mark.unit
def test_columns_when_imported_from_scraper_match_expected_order() -> None:
    assert COLUMNS == EXPECTED_COLUMNS


# =========================
# scrape_url (item)
# =========================
@pytest.mark.unit
def test_scrape_url_when_search_url_without_selenium_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A search URL with mocked empty extraction returns empty DataFrame."""
    monkeypatch.setattr(scraper_ebay, "extract_oxylabs_item_links", lambda url: [])
    monkeypatch.setattr(scraper_ebay, "_extract_item_links_from_search", lambda url, max_pages=1: [])

    df = scraper_ebay.scrape_url("https://www.ebay.com/sch/i.html?_nkw=omega")

    assert_empty_exact_columns(df)


@pytest.mark.unit
def test_scrape_url_when_item_browser_fetch_fails_returns_empty_exact_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_browser_error(url: str) -> None:
        raise RuntimeError(f"browser unavailable for {url}")

    monkeypatch.setattr(scraper_ebay, "fetch_oxylabs_html", lambda url: None)
    monkeypatch.setattr(scraper_ebay, "_scrape_item_with_firecrawl", raise_browser_error)

    df = scraper_ebay.scrape_url("https://www.ebay.com/itm/186641306493")

    assert_empty_exact_columns(df)


@pytest.mark.unit
def test_scrape_url_when_selenium_returns_html_parses_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simular la respuesta directa del cliente Firecrawl de scrape_url
    def mock_scrape(url):
        item = {
            "Stock": "999888777",
            "URL": url,
            "Make": "Tudor",
            "Model": "Black Bay",
            "Reference Number": "M79230N-0009",
            "Year": "2023",
            "Box": "Yes",
            "Papers": "Yes",
            "Original Price": "US $3,200.00",
        }
        return pd.DataFrame([item], columns=COLUMNS)

    monkeypatch.setattr(scraper_ebay, "_scrape_item_with_firecrawl", mock_scrape)

    df = scraper_ebay.scrape_url("https://www.ebay.com/itm/999888777")

    assert_exact_columns(df)
    record = df.iloc[0].to_dict()
    assert record["Make"] == "Tudor"
    assert record["Model"] == "Black Bay"
    assert record["Reference Number"] == "M79230N-0009"
    assert record["Year"] == "2023"
    assert record["Box"] == "Yes"
    assert record["Papers"] == "Yes"
    assert record["Stock"] == "999888777"
    assert "3,200" in record["Original Price"]


# =========================
# scrape_url (store/search)
# =========================
@pytest.mark.unit
def test_scrape_url_when_store_url_extracts_and_scrapes_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Store URL: extract item links → scrape each one."""
    fake_links = [
        "https://www.ebay.com/itm/111",
        "https://www.ebay.com/itm/222",
    ]

    def mock_scrape(url):
        make = "Rolex" if "111" in url else "Omega"
        model = "Daytona" if "111" in url else "Seamaster"
        price = "US $25,000.00" if "111" in url else "US $5,000.00"
        item = {
            "Stock": extract_item_id(url),
            "URL": url,
            "Make": make,
            "Model": model,
            "Reference Number": "123",
            "Year": "2020",
            "Box": "Yes",
            "Papers": "Yes",
            "Original Price": price,
        }
        return pd.DataFrame([item], columns=COLUMNS)

    monkeypatch.setattr(scraper_ebay, "fetch_item_links_for_search_url", lambda url: [])
    monkeypatch.setattr(scraper_ebay, "extract_oxylabs_item_links", lambda url: [])
    monkeypatch.setattr(
        scraper_ebay, "_extract_item_links_from_search", lambda url, max_pages=1: fake_links
    )
    monkeypatch.setattr(scraper_ebay, "_scrape_item", mock_scrape)
    monkeypatch.setattr(scraper_ebay.time, "sleep", lambda s: None)

    df = scraper_ebay.scrape_url(
        "https://www.ebay.com/sch/i.html?_ssn=chronodynamix&store_name=markswatchesusa"
    )

    assert_exact_columns(df)
    assert len(df) == 2
    assert df.iloc[0]["Make"] == "Rolex"
    assert df.iloc[1]["Make"] == "Omega"


@pytest.mark.unit
def test_extract_item_links_from_search_when_ebay_injects_shop_card_skips_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <ul>
      <li class="s-card">
        <a class="s-card__link" href="https://ebay.com/itm/987654321?itmmeta=abc">
          <div role="heading" aria-level="3" class="s-card__title">
            <span>Shop on eBay</span>
          </div>
        </a>
        <span>Brand New</span>
        <span>$20.00</span>
      </li>
      <li class="s-card">
        <a class="s-card__link" href="https://www.ebay.com/itm/999888777?hash=real">
          <div role="heading" aria-level="3" class="s-card__title">
            <span>OMEGA Seamaster 2511.81 W/ Box</span>
          </div>
        </a>
        <span>w2cllc 100% positivo (1,1K)</span>
      </li>
    </ul>
    """

    monkeypatch.setattr(scraper_ebay, "fetch_search_html", lambda url: html)

    links = scraper_ebay._extract_item_links_from_search(
        "https://www.ebay.com/sch/i.html?_ssn=w2cllc"
    )

    assert links == ["https://www.ebay.com/itm/999888777"]


@pytest.mark.unit
def test_extract_item_links_from_search_when_fast_mode_first_blocks_retries_basic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fast_html = "<html><body><p>blocked</p></body></html>"
    retry_html = """
    <ul>
      <li class="s-card">
        <a class="s-card__link" href="https://www.ebay.com/itm/405970836335?hash=real">
          <div role="heading" aria-level="3" class="s-card__title">
            <span>Rolex Datejust 36mm W/ B&P</span>
          </div>
        </a>
        <span>greglesley 100% positive</span>
      </li>
    </ul>
    """
    responses = iter([fast_html, retry_html])

    monkeypatch.setattr(scraper_ebay, "fetch_search_html", lambda url: next(responses))
    monkeypatch.setattr(scraper_ebay.time, "sleep", lambda seconds: None)

    links = scraper_ebay._extract_item_links_from_search(
        "https://www.ebay.com/sch/i.html?_ssn=greglesley&store_name=elevatedluxe"
    )

    assert links == ["https://www.ebay.com/itm/405970836335"]


@pytest.mark.unit
def test_scrape_url_when_unrecognized_ebay_url_returns_empty() -> None:
    df = scraper_ebay.scrape_url("https://www.ebay.com/something/weird")

    assert_empty_exact_columns(df)
