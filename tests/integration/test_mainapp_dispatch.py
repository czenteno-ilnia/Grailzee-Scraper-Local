from __future__ import annotations

import pandas as pd
import pytest
import requests_mock

try:
    import tkinter  # noqa: F401
except ImportError:
    pytest.skip("Tkinter is not available in this Python environment", allow_module_level=True)

import MainApp
from scraper_ebay import COLUMNS
from shopify_retrieval_types import (
    ShopifyCatalogSuccess,
    ShopifyProduct,
    ShopifyRetrievalSource,
    ShopifyEmptyCatalog,
    ShopifyHttpFailure,
    ShopifyPaginationFailure,
    ShopifySchemaFailure,
    ShopifyUnsupportedPlatform,
    ShopifyVariant,
)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.ebay.com/itm/123", True),
        ("http://chrono24.com/watch", True),
        ("str-item-card__link href", False),
        ("ebay.com/itm/123", False),
    ],
)
def test_is_valid_url(value: str, expected: bool) -> None:
    assert MainApp.is_valid_url(value) is expected


@pytest.mark.integration
def test_run_scraper_when_supported_brand_url_is_dispatched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.log = lambda msg: None
    monkeypatch.setattr(
        MainApp.scraper_chrono24,
        "scrape_multiple",
        lambda urls, existing_ids=None, progress_callback=None: pd.DataFrame([{
            "Stock": "1",
            "URL": urls[0],
            "Make": "Rolex",
            "Model": "Datejust",
            "Reference Number": "Ref",
            "Year": "2024",
            "Box": "Yes",
            "Papers": "Yes",
            "Original Price": "$1",
        }]),
    )

    df = app._dispatch("https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true")

    assert df is not None
    assert df.iloc[0]["Make"] == "Rolex"


@pytest.mark.integration
def test_run_scraper_when_url_is_unsupported_does_not_write_report(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    logs: list[str] = []
    app.log = logs.append

    df = app._dispatch("https://unsupported.example/watch")

    assert df is None
    assert logs == ["   ⚠️ Sitio no reconocido"]


class FakeEntry:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value


@pytest.mark.integration
def test_dispatch_when_shopify_retrieval_succeeds_maps_products_to_standard_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    logs: list[str] = []
    app.log = logs.append
    url = "https://dealer.example/products/speedmaster-professional"
    requested_urls: list[str] = []
    product = ShopifyProduct(
        product_id="product-42",
        handle="speedmaster-professional",
        title="Speedmaster Professional",
        vendor="Omega",
        variants=(ShopifyVariant(variant_id="variant-7", sku="310.30.42.50.01.001", price="7200.00"),),
        url=url,
    )

    def retrieve_shopify_products(requested_url: str) -> ShopifyCatalogSuccess:
        requested_urls.append(requested_url)
        return ShopifyCatalogSuccess(
            origin="https://dealer.example",
            source=ShopifyRetrievalSource.PRODUCT,
            collection_handle=None,
            products=(product,),
        )

    monkeypatch.setattr(MainApp.scraper_shopify, "retrieve_shopify_products", retrieve_shopify_products)

    dataframe = app._dispatch(url)

    assert requested_urls == [url]
    assert dataframe is not None
    assert list(dataframe.columns) == COLUMNS
    assert dataframe.to_dict(orient="records") == [
        {
            "Stock": "shopify:product-42:variant-7",
            "URL": url,
            "Make": "Omega",
            "Model": "Speedmaster Professional",
            "Reference Number": "310.30.42.50.01.001",
            "Year": "Missing information",
            "Box": "Missing information",
            "Papers": "Missing information",
            "Original Price": "7200.00",
            "Customized": "Missing information",
            "Category": "Missing information",
            "Seller": "Missing information",
        }
    ]
    assert logs == []


@pytest.mark.integration
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(
            ShopifyUnsupportedPlatform(
                url="https://invalid-store.example",
                detail="URL is not a supported Shopify shape",
            ),
            id="invalid-store",
        ),
        pytest.param(
            ShopifyUnsupportedPlatform(
                url="https://dealer.example",
                detail="Store did not confirm Shopify",
            ),
            id="unsupported-platform",
        ),
        pytest.param(
            ShopifyEmptyCatalog(url="https://dealer.example/products.json"),
            id="empty-catalog",
        ),
        pytest.param(
            ShopifyHttpFailure(
                url="https://dealer.example/products.json",
                status_code=None,
                detail="ConnectionError",
            ),
            id="request-error",
        ),
        pytest.param(
            ShopifySchemaFailure(
                url="https://dealer.example/products.json",
                detail="Response did not contain valid JSON",
            ),
            id="malformed-response",
        ),
        pytest.param(
            ShopifyPaginationFailure(
                url="https://dealer.example/products.json",
                detail="Catalog page limit reached before termination",
            ),
            id="pagination-failure",
        ),
    ],
)
def test_run_scraper_when_shopify_retrieval_fails_writes_visible_failure_without_recording_success_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    failure,
) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("failed-shopify")
    app.entry_oxy_user = FakeEntry()
    app.entry_oxy_pass = FakeEntry()
    app.progress = {}
    logs: list[str] = []
    app.log = logs.append
    app._set_status = lambda status: None
    app._update_latest_info = lambda: None
    url = "https://dealer.example/products/unknown"
    requested_urls: list[str] = []
    persisted: list[pd.DataFrame] = []

    def retrieve_shopify_products(requested_url: str):
        requested_urls.append(requested_url)
        return failure

    monkeypatch.setattr(MainApp.scraper_shopify, "retrieve_shopify_products", retrieve_shopify_products)
    monkeypatch.setattr(MainApp.dd, "known_ids", lambda: set())
    monkeypatch.setattr(MainApp.dd, "record_df", lambda dataframe: persisted.append(dataframe) or len(dataframe))
    monkeypatch.setitem(MainApp.settings, "report_dir", str(tmp_path))

    app._run_scraper([url])

    assert requested_urls == [url, url]
    assert persisted == []
    report = pd.read_csv(tmp_path / "failed-shopify.csv")
    assert report.to_dict(orient="records") == [
        {column: url if column == "URL" else MainApp.FAILED_NOTE for column in COLUMNS}
    ]
    assert any("Shopify:" in message for message in logs)


@pytest.mark.integration
def test_run_scraper_when_invalid_shopify_store_precedes_valid_store_records_both_outcomes_and_continues(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("mixed-shopify")
    app.entry_oxy_user = FakeEntry()
    app.entry_oxy_pass = FakeEntry()
    app.progress = {}
    app.log = lambda message: None
    app._set_status = lambda status: None
    app._update_latest_info = lambda: None
    invalid_url = "https://invalid-store.example/products/unknown"
    valid_url = "https://valid-store.example/products/speedmaster"
    requested_urls: list[str] = []
    persisted: list[pd.DataFrame] = []
    product = ShopifyProduct(
        product_id="product-42",
        handle="speedmaster",
        title="Speedmaster",
        vendor="Omega",
        variants=(ShopifyVariant(variant_id="variant-7", sku="sku-7", price="7200.00"),),
        url=valid_url,
    )

    def retrieve_shopify_products(requested_url: str):
        requested_urls.append(requested_url)
        if requested_url == invalid_url:
            return ShopifyUnsupportedPlatform(
                url=requested_url,
                detail="Store did not confirm Shopify",
            )
        return ShopifyCatalogSuccess(
            origin="https://valid-store.example",
            source=ShopifyRetrievalSource.PRODUCT,
            collection_handle=None,
            products=(product,),
        )

    monkeypatch.setattr(MainApp.scraper_shopify, "retrieve_shopify_products", retrieve_shopify_products)
    monkeypatch.setattr(MainApp.dd, "known_ids", lambda: set())
    monkeypatch.setattr(MainApp.dd, "record_df", lambda dataframe: persisted.append(dataframe) or len(dataframe))
    monkeypatch.setitem(MainApp.settings, "report_dir", str(tmp_path))

    app._run_scraper([invalid_url, valid_url])

    assert requested_urls == [invalid_url, valid_url, invalid_url]
    assert [dataframe["URL"].tolist() for dataframe in persisted] == [[valid_url]]
    report = pd.read_csv(tmp_path / "mixed-shopify.csv")
    assert report["URL"].tolist() == [valid_url, invalid_url]
    assert report.loc[0, "Stock"] == "shopify:product-42:variant-7"
    assert report.loc[1, "Make"] == MainApp.FAILED_NOTE


@pytest.mark.integration
def test_batch_csv_path_uses_report_name_and_slugifies(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("Rolex Batch #3")
    monkeypatch.setitem(MainApp.settings, "report_dir", "reportes")

    assert app._batch_csv_path() == "reportes/Rolex_Batch_3.csv"


@pytest.mark.integration
def test_batch_csv_path_defaults_to_timestamp_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("")
    monkeypatch.setitem(MainApp.settings, "report_dir", "reportes")

    csv_path = app._batch_csv_path()
    name = csv_path.split("/")[-1]
    assert name.startswith("batch_") and name.endswith(".csv")


@pytest.mark.integration
def test_run_scraper_retries_a_failed_url_once(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("failed")
    app.entry_oxy_user = FakeEntry()
    app.entry_oxy_pass = FakeEntry()
    app.progress = {}
    logs: list[str] = []
    app.log = logs.append
    app._set_status = lambda status: None
    app._update_latest_info = lambda: None
    calls: list[str] = []
    app._dispatch = lambda url, **kwargs: calls.append(url)
    monkeypatch.setitem(MainApp.settings, "report_dir", str(tmp_path))
    monkeypatch.setattr(MainApp.dd, "known_ids", lambda: set())

    app._run_scraper(["https://www.ebay.com/itm/123"], ["str-item-card__link href"])

    assert calls == ["https://www.ebay.com/itm/123"] * 2
    assert len(pd.read_csv(tmp_path / "failed.csv")) == 1
    assert logs[-1] == "   • str-item-card__link href"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("url", "known_ids", "expected"),
    [
        ("https://www.ebay.com/itm/123456?hash=abc", {("ebay", "123456")}, "123456"),
        (
            "https://www.chrono24.com/rolex/datejust--id987654.htm?SETLANG=en_US",
            {("chrono24", "https://www.chrono24.com/rolex/datejust--id987654.htm")},
            "https://www.chrono24.com/rolex/datejust--id987654.htm",
        ),
        ("https://www.ebay.com/sch/i.html?_nkw=omega", {("ebay", "123456")}, None),
        (
            "https://www.chrono24.com/search/index.htm?customerId=23766",
            {("chrono24", "https://www.chrono24.com/rolex/datejust--id987654.htm")},
            None,
        ),
    ],
)
def test_known_single_item_key_only_matches_direct_items(url, known_ids, expected) -> None:
    assert MainApp.known_single_item_key(url, known_ids) == expected


@pytest.mark.integration
def test_known_single_item_key_when_ebay_item_is_known_preserves_existing_key() -> None:
    url = "https://www.ebay.com/itm/123456?hash=abc"
    key = MainApp.known_single_item_key(url, {("ebay", "123456")})
    assert key == "123456"


@pytest.mark.integration
def test_run_scraper_when_known_shopify_product_skips_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    product_url = "https://timepiece-perfection.myshopify.com/products/speedmaster?utm_source=mail"
    known_key = "https://timepiece-perfection.myshopify.com/products/speedmaster"
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("known-shopify")
    app.entry_oxy_user = FakeEntry()
    app.entry_oxy_pass = FakeEntry()
    app.progress = {}
    logs: list[str] = []
    app.log = logs.append
    app._set_status = lambda status: None
    app._update_latest_info = lambda: None

    def fail_dispatch(url: str, **kwargs) -> None:
        raise AssertionError(f"Dispatch/client use is forbidden for a known product: {url}")

    app._dispatch = fail_dispatch
    monkeypatch.setitem(MainApp.settings, "report_dir", str(tmp_path))
    monkeypatch.setattr(MainApp.dd, "known_ids", lambda: {("Shopify", known_key)})

    app._run_scraper([product_url])
    assert "   ⏭️ Este item ya está scrapeado; no se agregará al CSV (0 requests)" in logs


@pytest.mark.integration
def test_known_single_item_key_when_custom_domain_product_is_known_returns_key() -> None:
    product_url = "https://watches.example/products/speedmaster?utm_source=mail"
    known_key = "https://watches.example/products/speedmaster"

    assert MainApp.known_single_item_key(product_url, {("Shopify", known_key)}) == known_key


@pytest.mark.integration
def test_known_single_item_key_when_unverified_custom_domain_product_is_unknown_returns_none() -> None:
    product_url = "https://watches.example/products/speedmaster?utm_source=mail"

    assert MainApp.known_single_item_key(product_url, set()) is None


@pytest.mark.integration
def test_run_scraper_when_known_verified_custom_shopify_product_skips_second_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    origin = "https://skip-verified-dealer.example"
    product_url = f"{origin}/products/speedmaster?utm_source=mail"
    known_key = f"{origin}/products/speedmaster"
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("known-custom-shopify")
    app.entry_oxy_user = FakeEntry()
    app.entry_oxy_pass = FakeEntry()
    app.progress = {}
    logs: list[str] = []
    app.log = logs.append
    app._set_status = lambda status: None
    app._update_latest_info = lambda: None

    def fail_dispatch(url: str, **kwargs) -> None:
        raise AssertionError(f"Dispatch/client use is forbidden for a known product: {url}")

    app._dispatch = fail_dispatch
    monkeypatch.setitem(MainApp.settings, "report_dir", str(tmp_path))
    monkeypatch.setattr(MainApp.dd, "known_ids", lambda: {("Shopify", known_key)})

    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{origin}/products/speedmaster.js", json={"id": 1, "handle": "speedmaster", "title": "Speedmaster"})
        result = MainApp.scraper_shopify.retrieve_shopify_products(product_url)
        app._run_scraper([product_url])

    assert isinstance(result, ShopifyCatalogSuccess)
    assert len(mocked_http.request_history) == 1
    assert "   ⏭️ Este item ya está scrapeado; no se agregará al CSV (0 requests)" in logs


@pytest.mark.integration
def test_known_single_item_key_preserves_ebay_and_chrono24_direct_item_keys() -> None:
    ebay_url = "https://www.ebay.com/itm/123456?hash=abc"
    chrono24_url = "https://www.chrono24.com/rolex/datejust--id987654.htm?SETLANG=en_US"
    existing_ids = {
        ("ebay", "123456"),
        ("chrono24", "https://www.chrono24.com/rolex/datejust--id987654.htm"),
    }

    assert MainApp.known_single_item_key(ebay_url, existing_ids) == "123456"
    assert MainApp.known_single_item_key(chrono24_url, existing_ids) == "https://www.chrono24.com/rolex/datejust--id987654.htm"


@pytest.mark.integration
def test_known_single_item_key_skips_repeat_myshopify_product_only_for_shopify_identity() -> None:
    url = "https://timepiece-perfection.myshopify.com/products/speedmaster?utm_source=mail"
    key = "https://timepiece-perfection.myshopify.com/products/speedmaster"

    assert MainApp.known_single_item_key(url, {("Shopify", key)}) == key
    assert MainApp.known_single_item_key(url, {("ebay", key)}) is None


@pytest.mark.integration
def test_run_scraper_keeps_shopify_stock_id_known_only_to_ebay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("cross-source-shopify")
    app.entry_oxy_user = FakeEntry()
    app.entry_oxy_pass = FakeEntry()
    app.progress = {}
    app.log = lambda message: None
    app._set_status = lambda status: None
    app._update_latest_info = lambda: None
    stock_id = "shopify:product-42:variant-7"
    shopify_url = "https://dealer.example/products/speedmaster"
    app._dispatch = lambda url, **kwargs: pd.DataFrame([{
        "Stock": stock_id,
        "URL": shopify_url,
        "Make": "Omega",
        "Model": "Speedmaster",
        "Reference Number": "",
        "Year": "",
        "Box": "",
        "Papers": "",
        "Original Price": "7200",
        "Customized": "",
        "Category": "",
        "Seller": "",
    }])
    persisted: list[pd.DataFrame] = []
    monkeypatch.setattr(MainApp.dd, "known_ids", lambda: {("ebay", stock_id)})
    monkeypatch.setattr(MainApp.dd, "record_df", lambda dataframe: persisted.append(dataframe) or 1)
    monkeypatch.setitem(MainApp.settings, "report_dir", str(tmp_path))

    app._run_scraper([shopify_url])

    assert pd.read_csv(tmp_path / "cross-source-shopify.csv")["Stock"].tolist() == [stock_id]
    assert len(persisted) == 1


@pytest.mark.integration
def test_localize_first_seen_for_mexico_csv() -> None:
    df = pd.DataFrame({"first_seen": ["2026-07-17T14:37:00Z", "2026-07-16T08:48:50", ""]})

    result = MainApp.localize_first_seen(df)

    assert result["first_seen"].tolist() == [
        "2026-07-17 08:37:00 -0600",
        "2026-07-16 08:48:50 -0600",
        "",
    ]
