from __future__ import annotations

import pytest
import requests_mock

from scraper_shopify import (
    ShopifyCatalogSuccess,
    ShopifyEmptyCatalog,
    ShopifyHttpFailure,
    ShopifySchemaFailure,
    retrieve_shopify_products,
)


@pytest.mark.unit
def test_collection_when_json_is_404_extracts_scoped_html_product_links() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    collection = f"{origin}/es-mx/collections/new-arrivals"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{collection}/products.json?limit=250&page=1", status_code=404)
        mocked_http.get(
            collection,
            text='''<a href="/es-mx/products/speedmaster">Speedmaster</a>
                     <a href="/es-mx/collections/new-arrivals/products/seamaster">Seamaster</a>''',
        )
        mocked_http.get(f"{origin}/es-mx/products/speedmaster.js", json=_product(1, "speedmaster"))
        mocked_http.get(f"{origin}/es-mx/products/seamaster.js", json=_product(2, "seamaster"))

        result = retrieve_shopify_products(collection)

    assert isinstance(result, ShopifyCatalogSuccess)
    assert result.collection_handle == "new-arrivals"
    assert [product.product_id for product in result.products] == ["1", "2"]
    assert [request.url for request in mocked_http.request_history] == [
        f"{collection}/products.json?limit=250&page=1",
        collection,
        f"{origin}/es-mx/products/speedmaster.js",
        f"{origin}/es-mx/products/seamaster.js",
    ]


@pytest.mark.unit
def test_collection_when_json_schema_is_invalid_follows_collection_next_page() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    collection = f"{origin}/collections/new-arrivals"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{collection}/products.json?limit=250&page=1", json={"products": "invalid"})
        mocked_http.get(
            collection,
            text='<a href="/products/speedmaster">Speedmaster</a><a rel="next" href="?page=2">Next</a>',
        )
        mocked_http.get(f"{collection}?page=2", text='<a href="/products/seamaster">Seamaster</a>')
        mocked_http.get(f"{origin}/products/speedmaster.js", json=_product(1, "speedmaster"))
        mocked_http.get(f"{origin}/products/seamaster.js", json=_product(2, "seamaster"))

        result = retrieve_shopify_products(collection)

    assert isinstance(result, ShopifyCatalogSuccess)
    assert [product.handle for product in result.products] == ["speedmaster", "seamaster"]
    assert [request.url for request in mocked_http.request_history] == [
        f"{collection}/products.json?limit=250&page=1",
        collection,
        f"{collection}?page=2",
        f"{origin}/products/speedmaster.js",
        f"{origin}/products/seamaster.js",
    ]


@pytest.mark.unit
def test_collection_html_fallback_when_product_links_repeat_fetches_each_handle_once() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    collection = f"{origin}/collections/new-arrivals"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{collection}/products.json?limit=250&page=1", status_code=404)
        mocked_http.get(
            collection,
            text='<a href="/products/speedmaster">One</a><a href="/products/speedmaster">Two</a>',
        )
        mocked_http.get(f"{origin}/products/speedmaster.js", json=_product(1, "speedmaster"))

        result = retrieve_shopify_products(collection)

    assert isinstance(result, ShopifyCatalogSuccess)
    assert [request.url for request in mocked_http.request_history].count(f"{origin}/products/speedmaster.js") == 1


@pytest.mark.unit
def test_collection_html_fallback_when_html_is_empty_returns_empty_catalog() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    collection = f"{origin}/collections/new-arrivals"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{collection}/products.json?limit=250&page=1", status_code=404)
        mocked_http.get(collection, text="")

        result = retrieve_shopify_products(collection)

    assert isinstance(result, ShopifyEmptyCatalog)


@pytest.mark.unit
def test_collection_html_fallback_when_html_has_no_product_links_returns_schema_failure() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    collection = f"{origin}/collections/new-arrivals"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{collection}/products.json?limit=250&page=1", json={"products": "invalid"})
        mocked_http.get(collection, text="<main><h1>New arrivals</h1>")

        result = retrieve_shopify_products(collection)

    assert isinstance(result, ShopifySchemaFailure)


@pytest.mark.unit
def test_collection_html_fallback_when_later_product_ajax_request_fails_returns_http_failure() -> None:
    origin = "https://timepiece-perfection.myshopify.com"
    collection = f"{origin}/collections/new-arrivals"
    with requests_mock.Mocker() as mocked_http:
        mocked_http.get(f"{collection}/products.json?limit=250&page=1", status_code=404)
        mocked_http.get(
            collection,
            text='<a href="/products/speedmaster">Speedmaster</a><a href="/products/seamaster">Seamaster</a>',
        )
        mocked_http.get(f"{origin}/products/speedmaster.js", json=_product(1, "speedmaster"))
        mocked_http.get(f"{origin}/products/seamaster.js", status_code=503)

        result = retrieve_shopify_products(collection)

    assert isinstance(result, ShopifyHttpFailure)
    assert result.status_code == 503


def _product(identifier: int, handle: str) -> dict[str, int | str]:
    return {"id": identifier, "handle": handle, "title": handle.title()}
