from __future__ import annotations

from bs4 import BeautifulSoup
import pytest

import chrono24_fetch
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
  <div class="m-b-2 d-flex justify-content-between">
    <div>Professional dealer <span class="flag"><img alt="us"></span></div>
    <div><span class="rating">5.0</span></div>
  </div>
  <button class="js-link-merchant-name p-a-0 link text-bold m-b-1">
    Sivils Luxury
  </button>
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


class FakeDriver:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def quit(self) -> None:
        self.calls.append("quit")


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
    def fake_collect_listing_urls(url: str, progress_callback=None) -> list[str]:
        assert "customerId=23766" in url
        return ["https://www.chrono24.com/rolex/datejust-36--id111111.htm"]

    def fake_get_soup(url: str) -> BeautifulSoup:
        assert url == "https://www.chrono24.com/rolex/datejust-36--id111111.htm"
        return BeautifulSoup(DETAIL_HTML, "html.parser")

    monkeypatch.setattr(scraper_chrono24, "collect_listing_urls", fake_collect_listing_urls)
    monkeypatch.setattr(scraper_chrono24, "_get_soup_with_requests", fake_get_soup)

    logs: list[str] = []
    df = scraper_chrono24.scrape_multiple(
        ["https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true"],
        progress_callback=logs.append,
    )

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
        "Customized": "Missing",
        "Seller": "Sivils Luxury",
    }]
    assert logs == ["   Chrono24: procesando 1 listings", "   Chrono24: scrapeando item 1/1: https://www.chrono24.com/rolex/datejust-36--id111111.htm"]


@pytest.mark.integration
def test_scrape_multiple_when_listing_already_exists_skips_detail_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    existing_url = "https://www.chrono24.com/rolex/datejust-36--id111111.htm"

    def fake_collect_listing_urls(url: str, progress_callback=None) -> list[str]:
        assert "customerId=23766" in url
        return [existing_url]

    def fail_get_soup(url: str) -> BeautifulSoup:
        raise AssertionError(f"Detail page should not be fetched for existing listing: {url}")

    monkeypatch.setattr(scraper_chrono24, "collect_listing_urls", fake_collect_listing_urls)
    monkeypatch.setattr(scraper_chrono24, "_get_soup_with_requests", fail_get_soup)

    df = scraper_chrono24.scrape_multiple(
        ["https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true"],
        existing_ids={existing_url},
    )

    assert df.empty
    assert list(df.columns) == scraper_chrono24.COLUMNS


@pytest.mark.integration
def test_scrape_multiple_when_detail_requests_blocked_uses_browser_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    listing_url = "https://www.chrono24.com/rolex/datejust-36--id111111.htm"
    calls: list[str] = []

    def fake_collect_listing_urls(url: str, progress_callback=None) -> list[str]:
        return [listing_url]

    def fake_get_soup_with_requests(url: str) -> BeautifulSoup | None:
        calls.append(f"requests:{url}")
        return None

    def fake_get_soup_with_browser(url: str) -> BeautifulSoup:
        calls.append(f"browser:{url}")
        return BeautifulSoup(DETAIL_HTML, "html.parser")

    monkeypatch.setattr(scraper_chrono24, "collect_listing_urls", fake_collect_listing_urls)
    monkeypatch.setattr(scraper_chrono24, "_get_soup_with_requests", fake_get_soup_with_requests)
    monkeypatch.setattr(scraper_chrono24, "_get_soup_with_browser", fake_get_soup_with_browser)

    df = scraper_chrono24.scrape_multiple([
        "https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true"
    ])

    assert len(df) == 1
    assert calls == [f"requests:{listing_url}", f"browser:{listing_url}"]


@pytest.mark.integration
def test_get_soup_with_browser_uses_regular_selenium_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_make_driver() -> FakeDriver:
        calls.append("make_driver")
        return FakeDriver(calls)

    def fake_soup_from_driver(driver: FakeDriver, url: str) -> BeautifulSoup:
        calls.append(f"soup:{url}")
        return BeautifulSoup("<html><body>ok</body></html>", "html.parser")

    monkeypatch.setattr(chrono24_fetch, "make_selenium_driver", fake_make_driver)
    monkeypatch.setattr(chrono24_fetch, "soup_from_driver", fake_soup_from_driver)

    soup = chrono24_fetch.get_soup_with_browser("https://www.chrono24.com/example")

    assert soup.get_text(" ", strip=True) == "ok"
    assert calls == ["make_driver", "soup:https://www.chrono24.com/example", "quit"]
