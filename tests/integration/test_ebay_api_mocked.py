from __future__ import annotations

import pytest

import scraper_ebay


@pytest.mark.integration
def test_scrape_url_when_ebay_url_has_no_item_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scraper_ebay, "extract_oxylabs_item_links", lambda url, **kwargs: [])

    df = scraper_ebay.scrape_url("https://www.ebay.com/sch/i.html?_nkw=omega")

    assert list(df.columns) == [
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
    assert df.empty


@pytest.mark.integration
def test_scrape_url_when_selenium_mocked_returns_full_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration: scrape_url with mocked Selenium returns parsed data correctly."""
    fixture_html = """
    <html><body>
      <div class="ux-layout-section__textual-display--itemId">
        <span class="ux-textspans--BOLD">999888777</span>
      </div>
      <dl>
        <dt class="ux-labels-values__labels">Brand</dt>
        <dd class="ux-labels-values__values">Tudor</dd>
        <dt class="ux-labels-values__labels">Model</dt>
        <dd class="ux-labels-values__values">Black Bay</dd>
        <dt class="ux-labels-values__labels">Reference Number</dt>
        <dd class="ux-labels-values__values">M79230N-0009</dd>
        <dt class="ux-labels-values__labels">With Original Box/Packaging</dt>
        <dd class="ux-labels-values__values">Yes</dd>
        <dt class="ux-labels-values__labels">With Papers</dt>
        <dd class="ux-labels-values__values">Yes</dd>
      </dl>
      <div data-testid="x-price-primary"><span>US $3,200.00</span></div>
    </body></html>
    """

    monkeypatch.setattr(scraper_ebay, "_fetch_item_html", lambda url: fixture_html)

    df = scraper_ebay.scrape_url("https://www.ebay.com/itm/999888777")

    record = df.iloc[0].to_dict()
    assert record["Make"] == "Tudor"
    assert record["Model"] == "Black Bay"
    assert record["Reference Number"] == "M79230N-0009"
    assert record["Stock"] == "999888777"
