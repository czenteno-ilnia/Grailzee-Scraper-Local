from __future__ import annotations

import pytest

import scraper_shopify
from scraper_shopify import ShopifyCatalogSuccess, retrieve_shopify_products


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self.text = "{}"
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


@pytest.mark.unit
def test_retrieve_shopify_products_when_default_http_get_is_used_delegates_to_requests_get(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, float]] = []

    def fake_get(url: str, *, timeout: float) -> _FakeResponse:
        calls.append((url, timeout))
        return _FakeResponse(
            200,
            {
                "id": 42,
                "handle": "speedmaster",
                "title": "Speedmaster",
                "variants": [{"id": 7, "sku": "sku-7", "price": "7200.00"}],
            },
        )

    monkeypatch.setattr(scraper_shopify.requests, "get", fake_get)

    result = retrieve_shopify_products("https://timepiece-perfection.myshopify.com/products/speedmaster")

    assert calls == [("https://timepiece-perfection.myshopify.com/products/speedmaster.js", 20.0)]
    assert isinstance(result, ShopifyCatalogSuccess)
    assert [product.product_id for product in result.products] == ["42"]
