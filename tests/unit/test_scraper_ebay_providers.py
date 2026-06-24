from __future__ import annotations

import pandas as pd
import pytest

import ebay_oxylabs_client
import ebay_oxylabs_listing
import scraper_ebay
from scraper_ebay import COLUMNS, extract_item_id


class OxylabsResponse:
    def __init__(self, status_code, results=None):
        self.status_code = status_code
        self._results = [] if results is None else results

    def json(self):
        return {"results": self._results}


@pytest.mark.unit
def test_scrape_url_when_oxylabs_returns_links_skips_firecrawl_and_browse_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_backend(url):
        raise AssertionError(f"Backend should not run for {url}")

    def mock_scrape(url):
        item = {
            "Stock": extract_item_id(url),
            "URL": url,
            "Make": "Omega",
            "Model": "Seamaster Aqua Terra",
            "Reference Number": "231.10.42.21.01.002",
            "Year": "2019",
            "Box": "Yes",
            "Papers": "Yes",
            "Original Price": "US $4,950.00",
        }
        return pd.DataFrame([item], columns=COLUMNS)

    monkeypatch.setattr(scraper_ebay, "fetch_item_links_for_search_url", fail_backend)
    monkeypatch.setattr(scraper_ebay, "extract_oxylabs_item_links", lambda url: ["https://www.ebay.com/itm/287244457749"])
    monkeypatch.setattr(scraper_ebay, "_extract_item_links_from_search", fail_backend)
    monkeypatch.setattr(scraper_ebay, "_scrape_item", mock_scrape)
    monkeypatch.setattr(scraper_ebay, "is_already_scraped", lambda item_id: False)

    df = scraper_ebay.scrape_url(
        "https://www.ebay.com/sch/i.html?_ssn=greglesley&store_name=elevatedluxe"
    )

    assert len(df) == 1
    assert df.iloc[0]["Stock"] == "287244457749"


@pytest.mark.unit
def test_scrape_item_when_oxylabs_returns_specs_skips_firecrawl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item_html = """
    <html><body>
      <div class="ux-layout-section__textual-display--itemId">
        <span class="ux-textspans--BOLD">287244457749</span>
      </div>
      <dl>
        <dt class="ux-labels-values__labels">Brand</dt><dd class="ux-labels-values__values">Omega</dd>
        <dt class="ux-labels-values__labels">Model</dt><dd class="ux-labels-values__values">Seamaster Aqua Terra</dd>
        <dt class="ux-labels-values__labels">Reference Number</dt><dd class="ux-labels-values__values">231.10.42.21.01.002</dd>
      </dl>
      <div data-testid="x-price-primary"><span>US $4,950.00</span></div>
    </body></html>
    """

    def fail_firecrawl(url):
        raise AssertionError(f"Firecrawl should not run for {url}")

    monkeypatch.setattr(scraper_ebay, "fetch_oxylabs_html", lambda url: item_html)
    monkeypatch.setattr(scraper_ebay, "_scrape_item_with_firecrawl", fail_firecrawl)
    monkeypatch.setattr(scraper_ebay, "mark_as_scraped", lambda item_id, url: None)

    df = scraper_ebay._scrape_item("https://www.ebay.com/itm/287244457749")

    assert len(df) == 1
    assert df.iloc[0]["Make"] == "Omega"
    assert df.iloc[0]["Model"] == "Seamaster Aqua Terra"


@pytest.mark.unit
def test_extract_oxylabs_item_links_when_store_has_next_page_collects_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page_1 = """
    <html><body>
      <article class="str-item-card StoreFrontItemCard">
        <a href="https://www.ebay.com/itm/111?hash=a">Watch One</a>
      </article>
      <a aria-label="Next page" href="https://www.ebay.com/str/store?_pgn=2">Next</a>
    </body></html>
    """
    page_2 = """
    <html><body>
      <article class="str-item-card StoreFrontItemCard">
        <a href="https://www.ebay.com/itm/222?hash=b">Watch Two</a>
      </article>
    </body></html>
    """
    fetched_urls = []

    def fake_fetch(url):
        fetched_urls.append(url)
        if "_pgn=2" in url:
            return page_2
        return page_1

    monkeypatch.setattr(ebay_oxylabs_listing, "fetch_oxylabs_html", fake_fetch)

    links = ebay_oxylabs_listing.extract_oxylabs_item_links(
        "https://www.ebay.com/str/store/Jewelry-Watches/_i.html?_sacat=281",
        max_pages=5,
    )

    assert links == ["https://www.ebay.com/itm/111", "https://www.ebay.com/itm/222"]
    assert all("_ipg=240" in url for url in fetched_urls)


@pytest.mark.unit
def test_fetch_oxylabs_html_when_item_url_uses_ebay_product_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payloads = []

    def fake_post(url, auth, json, timeout):
        captured_payloads.append(json)
        return OxylabsResponse(200, [{"content": "<html>item</html>"}])

    monkeypatch.setenv("OXYLABS_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PASSWORD", "pass")
    monkeypatch.setattr(ebay_oxylabs_client.requests, "post", fake_post)

    html = ebay_oxylabs_client.fetch_oxylabs_html("https://www.ebay.com/itm/336642745734")

    assert html == "<html>item</html>"
    assert captured_payloads == [
        {
            "source": "ebay_product",
            "product_id": "336642745734",
            "render": "html",
        }
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "listing_url",
    [
        "https://www.ebay.com/str/store/Jewelry-Watches/_i.html?_sacat=281",
        "https://www.ebay.com/sch/i.html?_ssn=greglesley&store_name=elevatedluxe",
    ],
)
def test_fetch_oxylabs_html_when_listing_url_keeps_universal_payload(
    monkeypatch: pytest.MonkeyPatch,
    listing_url: str,
) -> None:
    captured_payloads = []

    def fake_post(url, auth, json, timeout):
        captured_payloads.append(json)
        return OxylabsResponse(200, [{"content": "<html>listing</html>"}])

    monkeypatch.setenv("OXYLABS_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PASSWORD", "pass")
    monkeypatch.setattr(ebay_oxylabs_client.requests, "post", fake_post)

    html = ebay_oxylabs_client.fetch_oxylabs_html(listing_url)

    assert html == "<html>listing</html>"
    assert captured_payloads == [
        {
            "source": "universal",
            "url": listing_url,
            "geo_location": "United States",
        }
    ]


@pytest.mark.unit
def test_fetch_oxylabs_html_when_provider_fails_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url, auth, json, timeout):
        return OxylabsResponse(500)

    monkeypatch.setenv("OXYLABS_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PASSWORD", "pass")
    monkeypatch.setattr(ebay_oxylabs_client.requests, "post", fake_post)

    html = ebay_oxylabs_client.fetch_oxylabs_html("https://www.ebay.com/itm/336642745734")

    assert html is None


@pytest.mark.unit
def test_fetch_oxylabs_html_when_credentials_missing_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_post(url, auth, json, timeout):
        raise AssertionError("Oxylabs request should not run without credentials")

    monkeypatch.setenv("OXYLABS_USERNAME", "")
    monkeypatch.setenv("OXYLABS_PASSWORD", "")
    monkeypatch.setattr(ebay_oxylabs_client.requests, "post", fail_post)

    html = ebay_oxylabs_client.fetch_oxylabs_html("https://www.ebay.com/itm/336642745734")

    assert html is None


@pytest.mark.unit
@pytest.mark.parametrize("results", [[], [{"content": ""}]])
def test_fetch_oxylabs_html_when_content_missing_returns_none(
    monkeypatch: pytest.MonkeyPatch,
    results,
) -> None:
    def fake_post(url, auth, json, timeout):
        return OxylabsResponse(200, results)

    monkeypatch.setenv("OXYLABS_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PASSWORD", "pass")
    monkeypatch.setattr(ebay_oxylabs_client.requests, "post", fake_post)

    html = ebay_oxylabs_client.fetch_oxylabs_html("https://www.ebay.com/itm/336642745734")

    assert html is None


@pytest.mark.unit
def test_scrape_url_when_oxylabs_empty_uses_firecrawl_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_links = ["https://www.ebay.com/itm/287244457749"]

    def fail_browse_api(url):
        raise AssertionError(f"Browse API should not run for {url}")

    def mock_scrape(url):
        item = {
            "Stock": extract_item_id(url),
            "URL": url,
            "Make": "Omega",
            "Model": "Seamaster Aqua Terra",
            "Reference Number": "231.10.42.21.01.002",
            "Year": "2019",
            "Box": "Yes",
            "Papers": "Yes",
            "Original Price": "US $4,950.00",
        }
        return pd.DataFrame([item], columns=COLUMNS)

    monkeypatch.setattr(scraper_ebay, "fetch_item_links_for_search_url", fail_browse_api)
    monkeypatch.setattr(scraper_ebay, "extract_oxylabs_item_links", lambda url: [])
    monkeypatch.setattr(scraper_ebay, "_extract_item_links_from_search", lambda url: fake_links)
    monkeypatch.setattr(scraper_ebay, "_scrape_item", mock_scrape)
    monkeypatch.setattr(scraper_ebay, "is_already_scraped", lambda item_id: False)

    df = scraper_ebay.scrape_url(
        "https://www.ebay.com/sch/i.html?_ssn=greglesley&store_name=elevatedluxe"
    )

    assert len(df) == 1
    assert df.iloc[0]["Stock"] == "287244457749"
