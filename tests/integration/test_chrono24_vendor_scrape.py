from __future__ import annotations

from bs4 import BeautifulSoup
import pytest

import scraper_chrono24


SEARCH_PAGE_1 = """
<html><body>
  <a href="/rolex/datejust-36--id111111.htm">Rolex Datejust</a>
  <a href="https://www.chrono24.com/omega/speedmaster--id222222.htm?query=x">Omega</a>
  <a aria-label="Next" href="/search/index.htm?customerId=23766&dosearch=true&page=2">Next</a>
</body></html>
"""

SEARCH_PAGE_2 = """
<html><body>
  <a href="/patekphilippe/calatrava--id333333.htm">Patek Philippe</a>
</body></html>
"""

DETAIL_HTML = """
<html><body>
  <h1>Rolex Datejust 36</h1>
  <div data-testid="price">$8,750</div>
  <table>
    <tr><th>Listing code</th><td>ABC123</td></tr>
    <tr><th>Brand</th><td>Rolex</td></tr>
    <tr><th>Model</th><td>Datejust 36</td></tr>
    <tr><th>Reference number</th><td>126234</td></tr>
    <tr><th>Year of production</th><td>2021</td></tr>
    <tr><th>Scope of delivery</th><td>Original box, original papers</td></tr>
  </table>
</body></html>
"""


@pytest.mark.integration
def test_collect_listing_urls_when_vendor_search_has_multiple_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = {
        "https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true": SEARCH_PAGE_1,
        "https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true&page=2": SEARCH_PAGE_2,
    }

    def fake_get_soup(url: str) -> BeautifulSoup:
        return BeautifulSoup(pages[url], "html.parser")

    monkeypatch.setattr(scraper_chrono24, "_get_soup_with_requests", fake_get_soup)

    urls = scraper_chrono24.collect_listing_urls(
        "https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true"
    )

    assert urls == [
        "https://www.chrono24.com/rolex/datejust-36--id111111.htm",
        "https://www.chrono24.com/omega/speedmaster--id222222.htm",
        "https://www.chrono24.com/patekphilippe/calatrava--id333333.htm",
    ]


@pytest.mark.integration
def test_scrape_multiple_when_input_is_vendor_search_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_collect_listing_urls(url: str) -> list[str]:
        assert "customerId=23766" in url
        return ["https://www.chrono24.com/rolex/datejust-36--id111111.htm"]

    def fake_get_soup(url: str) -> BeautifulSoup:
        assert url == "https://www.chrono24.com/rolex/datejust-36--id111111.htm"
        return BeautifulSoup(DETAIL_HTML, "html.parser")

    monkeypatch.setattr(scraper_chrono24, "collect_listing_urls", fake_collect_listing_urls)
    monkeypatch.setattr(scraper_chrono24, "_get_soup_with_requests", fake_get_soup)

    df = scraper_chrono24.scrape_multiple([
        "https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true"
    ])

    assert df.to_dict(orient="records") == [{
        "Stock": "ABC123",
        "URL": "https://www.chrono24.com/rolex/datejust-36--id111111.htm",
        "Make": "Rolex",
        "Model": "Datejust 36",
        "Reference Number": "126234",
        "Year": "2021",
        "Box": "Yes",
        "Papers": "Yes",
        "Original Price": "$8,750",
    }]
