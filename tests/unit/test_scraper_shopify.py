from __future__ import annotations

import pytest
import requests
import requests_mock

from scraper_shopify import (
    ShopifyCatalogSuccess,
    ShopifyEmptyCatalog,
    ShopifyHttpFailure,
    ShopifyPaginationFailure,
    ShopifySchemaFailure,
    ShopifyUnsupportedPlatform,
    direct_product_key,
    normalize_store_origin,
    retrieve_shopify_products,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://timepiece-perfection.myshopify.com/?utm_source=mail#catalog",
            "https://timepiece-perfection.myshopify.com",
        ),
        (
            "http://timepiece-perfection.myshopify.com/collections/new-arrivals?sort_by=created-descending",
            "https://timepiece-perfection.myshopify.com",
        ),
        (
            "https://timepiece-perfection.myshopify.com/products/speedmaster-professional?variant=123#details",
            "https://timepiece-perfection.myshopify.com",
        ),
        (
            "https://timepiece-perfection.myshopify.com/es-mx/collections/new-arrivals?sort_by=created-descending",
            "https://timepiece-perfection.myshopify.com",
        ),
        ("https://timepiece-perfection.myshopify.com", "https://timepiece-perfection.myshopify.com"),
    ],
)
def test_normalize_store_origin_when_supported_shopify_url_removes_path_and_tracking(
    url: str,
    expected: str,
) -> None:
    assert normalize_store_origin(url) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "ftp://timepiece-perfection.myshopify.com/products/watch",
        "https://",
        "https://timepiece..myshopify.com/products/watch",
        "https://-watches.example/products/watch",
        "https://watches.example:invalid/products/watch",
        "https://watches.example",
        "https://watches.example/products/speedmaster-professional",
        "https://www.ebay.com/itm/123456",
        "https://www.chrono24.com/rolex/datejust--id123.htm",
        "https://catalog.example/catalog/watches",
    ],
)
def test_normalize_store_origin_when_url_is_malformed_or_not_shopify_returns_none(url: str) -> None:
    assert normalize_store_origin(url) is None


@pytest.mark.unit
def test_direct_product_key_when_shopify_product_has_tracking_is_stable() -> None:
    assert direct_product_key(
        "https://timepiece-perfection.myshopify.com/products/speedmaster-professional/?utm_source=mail#details"
    ) == "https://timepiece-perfection.myshopify.com/products/speedmaster-professional"
    assert direct_product_key(
        "https://timepiece-perfection.myshopify.com/es-mx/products/speedmaster-professional?variant=123"
    ) == "https://timepiece-perfection.myshopify.com/products/speedmaster-professional"


@pytest.mark.unit
def test_direct_product_key_when_custom_domain_has_not_been_verified_returns_none() -> None:
    assert direct_product_key("https://watches.example/products/speedmaster-professional") is None


@pytest.mark.unit
def test_direct_product_key_when_custom_domain_product_response_confirms_shopify_is_available() -> None:
    origin = "https://verified-dealer.example"
    product_url = f"{origin}/products/speedmaster-professional?utm_source=mail"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{origin}/products/speedmaster-professional.js", json=_product(1, "speedmaster-professional"))

        result = retrieve_shopify_products(product_url)

    assert isinstance(result, ShopifyCatalogSuccess)
    assert direct_product_key(product_url) == f"{origin}/products/speedmaster-professional"


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "https://timepiece-perfection.myshopify.com",
        "https://timepiece-perfection.myshopify.com/collections/new-arrivals",
        "https://timepiece-perfection.myshopify.com/catalog/watches",
    ],
)
def test_direct_product_key_when_url_is_not_a_direct_product_returns_none(url: str) -> None:
    assert direct_product_key(url) is None


@pytest.mark.unit
def test_retrieve_shopify_products_when_catalog_spans_pages_returns_distinct_products() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(
            f"{origin}/products.json?limit=250&page=1",
            json={"products": [_product(1, "speedmaster"), _product(2, "seamaster")]},
        )
        mocked_http.get(
            f"{origin}/products.json?limit=250&page=2",
            json={"products": [_product(3, "constellation")]},
        )
        mocked_http.get(f"{origin}/products.json?limit=250&page=3", json={"products": []})

        result = retrieve_shopify_products(origin)

    assert isinstance(result, ShopifyCatalogSuccess)
    assert [product.product_id for product in result.products] == ["1", "2", "3"]
    assert [request.url for request in mocked_http.request_history] == [
        f"{origin}/products.json?limit=250&page=1",
        f"{origin}/products.json?limit=250&page=2",
        f"{origin}/products.json?limit=250&page=3",
    ]


@pytest.mark.unit
def test_retrieve_shopify_products_when_catalog_pages_repeat_products_deduplicates_by_product_id() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(
            f"{origin}/products.json?limit=250&page=1",
            json={"products": [_product(1, "speedmaster")]},
        )
        mocked_http.get(
            f"{origin}/products.json?limit=250&page=2",
            json={"products": [_product(1, "speedmaster"), _product(2, "seamaster")]},
        )
        mocked_http.get(f"{origin}/products.json?limit=250&page=3", json={"products": []})

        result = retrieve_shopify_products(origin)

    assert isinstance(result, ShopifyCatalogSuccess)
    assert [product.product_id for product in result.products] == ["1", "2"]


@pytest.mark.unit
def test_retrieve_shopify_products_when_catalog_reaches_empty_page_stops_pagination() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(
            f"{origin}/products.json?limit=250&page=1",
            json={"products": [_product(1, "speedmaster")]},
        )
        mocked_http.get(f"{origin}/products.json?limit=250&page=2", json={"products": []})

        result = retrieve_shopify_products(origin)

    assert isinstance(result, ShopifyCatalogSuccess)
    assert len(mocked_http.request_history) == 2


@pytest.mark.unit
def test_retrieve_shopify_products_when_collection_url_uses_collection_endpoint_preserves_scope() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(
            f"{origin}/collections/new-arrivals/products.json?limit=250&page=1",
            json={"products": [_product(1, "speedmaster")]},
        )
        mocked_http.get(
            f"{origin}/collections/new-arrivals/products.json?limit=250&page=2",
            json={"products": []},
        )

        result = retrieve_shopify_products(f"{origin}/collections/new-arrivals")

    assert isinstance(result, ShopifyCatalogSuccess)
    assert result.collection_handle == "new-arrivals"
    assert [request.url for request in mocked_http.request_history] == [
        f"{origin}/collections/new-arrivals/products.json?limit=250&page=1",
        f"{origin}/collections/new-arrivals/products.json?limit=250&page=2",
    ]


@pytest.mark.unit
def test_retrieve_shopify_products_when_direct_product_url_uses_localized_js_endpoint() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(
            f"{origin}/es-mx/products/speedmaster.js",
            json=_product(1, "speedmaster"),
        )

        result = retrieve_shopify_products(f"{origin}/es-mx/products/speedmaster?variant=123")

    assert isinstance(result, ShopifyCatalogSuccess)
    assert result.is_direct_product
    assert result.products[0].url == f"{origin}/es-mx/products/speedmaster"


@pytest.mark.unit
def test_retrieve_shopify_products_when_response_json_is_malformed_returns_schema_failure() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{origin}/products.json?limit=250&page=1", text="{not json")

        result = retrieve_shopify_products(origin)

    assert isinstance(result, ShopifySchemaFailure)


@pytest.mark.unit
def test_retrieve_shopify_products_when_catalog_schema_is_invalid_returns_schema_failure() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{origin}/products.json?limit=250&page=1", json={"products": "not-a-list"})

        result = retrieve_shopify_products(origin)

    assert isinstance(result, ShopifySchemaFailure)


@pytest.mark.unit
def test_retrieve_shopify_products_when_request_fails_returns_http_failure() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(
            f"{origin}/products.json?limit=250&page=1",
            exc=requests.ConnectionError("unavailable"),
        )

        result = retrieve_shopify_products(origin)

    assert isinstance(result, ShopifyHttpFailure)
    assert result.status_code is None


@pytest.mark.unit
def test_retrieve_shopify_products_when_catalog_is_empty_returns_empty_catalog_failure() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{origin}/products.json?limit=250&page=1", json={"products": []})

        result = retrieve_shopify_products(origin)

    assert isinstance(result, ShopifyEmptyCatalog)


@pytest.mark.unit
def test_retrieve_shopify_products_when_pagination_never_terminates_returns_pagination_failure() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(
            f"{origin}/products.json?limit=250&page=1",
            json={"products": [_product(1, "speedmaster")]},
        )
        mocked_http.get(
            f"{origin}/products.json?limit=250&page=2",
            json={"products": [_product(2, "seamaster")]},
        )

        result = retrieve_shopify_products(origin, max_catalog_pages=2)

    assert isinstance(result, ShopifyPaginationFailure)


@pytest.mark.unit
def test_retrieve_shopify_products_when_custom_domain_response_is_not_shopify_rejects_platform() -> None:
    origin = "https://watches.example"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{origin}/products.json?limit=250&page=1", json={"items": []})

        result = retrieve_shopify_products(origin)

    assert isinstance(result, ShopifyUnsupportedPlatform)


def _product(identifier: int, handle: str) -> dict[str, int | str]:
    return {"id": identifier, "handle": handle, "title": handle.title()}
