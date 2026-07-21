from __future__ import annotations

from json import JSONDecodeError
from typing import Final

import requests

try:
    from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
except ImportError:
    from json import JSONDecodeError as RequestsJSONDecodeError

from shopify_collection_html import extract_collection_html_page
from shopify_product_json import parse_product
from shopify_url import ShopifyUrlTarget as _ShopifyUrl
from shopify_url import _parse_shopify_url, direct_product_key, normalize_store_origin
from shopify_url import remember_verified_direct_product_key
from shopify_url import verified_direct_product_key
from shopify_retrieval_types import (
    JsonValue,
    ShopifyCatalogSuccess,
    ShopifyEmptyCatalog,
    ShopifyHttpFailure,
    ShopifyHttpGet,
    ShopifyHttpResponse,
    ShopifyPaginationFailure,
    ShopifyProduct,
    ShopifyRetrievalFailure,
    ShopifyRetrievalResult,
    ShopifyRetrievalSource,
    ShopifySchemaFailure,
    ShopifyUnsupportedPlatform,
)


_CATALOG_PAGE_SIZE: Final = 250
_MAX_CATALOG_PAGES: Final = 100
_MAX_COLLECTION_HTML_PAGES: Final = 20
_REQUEST_TIMEOUT_SECONDS: Final = 20.0


class _ShopifyHttpResponseAdapter:
    __slots__ = ("_response", "status_code", "text")

    _response: requests.Response
    status_code: int
    text: str

    def __init__(self, response: requests.Response) -> None:
        self._response = response
        self.status_code = response.status_code
        self.text = response.text

    def json(self) -> JsonValue:
        return self._response.json()


def _shopify_http_get(url: str, *, timeout: float) -> ShopifyHttpResponse:
    response = requests.get(url, timeout=timeout)
    return _ShopifyHttpResponseAdapter(response)

def retrieve_shopify_products(
    url: str,
    *,
    http_get: ShopifyHttpGet = _shopify_http_get,
    max_catalog_pages: int = _MAX_CATALOG_PAGES,
) -> ShopifyRetrievalResult:
    """Retrieve a Shopify catalog or direct product through a typed result."""
    candidate = _parse_shopify_url(url, require_myshopify=False)
    if candidate is None:
        return ShopifyUnsupportedPlatform(url=url, detail="URL is not a supported Shopify shape")

    match candidate.source:
        case ShopifyRetrievalSource.PRODUCT:
            return _retrieve_direct_product(candidate, http_get)
        case ShopifyRetrievalSource.CATALOG | ShopifyRetrievalSource.COLLECTION:
            return _retrieve_catalog(candidate, http_get, max_catalog_pages)
        case _:
            raise AssertionError("Unknown Shopify retrieval source")


def _retrieve_direct_product(candidate: _ShopifyUrl, http_get: ShopifyHttpGet) -> ShopifyRetrievalResult:
    return _retrieve_product_handle(candidate, candidate.product_handle, http_get)


def _retrieve_product_handle(
    candidate: _ShopifyUrl,
    product_handle: str | None,
    http_get: ShopifyHttpGet,
) -> ShopifyRetrievalResult:
    match product_handle:
        case None:
            return _schema_failure(candidate, candidate.origin, "Product URL is missing a handle")
        case str() as handle:
            return _retrieve_product_json(candidate, handle, http_get)


def _retrieve_product_json(
    candidate: _ShopifyUrl,
    product_handle: str,
    http_get: ShopifyHttpGet,
) -> ShopifyRetrievalResult:
    response_url = f"{_localized_path(candidate)}/products/{product_handle}.js"
    payload = _fetch_json(candidate, response_url, http_get)
    match payload:
        case ShopifyUnsupportedPlatform() | ShopifyHttpFailure() | ShopifySchemaFailure():
            return payload
        case ShopifyEmptyCatalog() | ShopifyPaginationFailure():
            return payload
        case _:
            product = parse_product(payload, _localized_path(candidate))
            if product is None:
                return _schema_failure(candidate, response_url, "Direct product response has an invalid product schema")
            return _success(candidate, (product,))


def _retrieve_catalog(
    candidate: _ShopifyUrl,
    http_get: ShopifyHttpGet,
    max_catalog_pages: int,
) -> ShopifyRetrievalResult:
    if max_catalog_pages < 1:
        return ShopifyPaginationFailure(url=candidate.origin, detail="Catalog page limit must be positive")

    products: list[ShopifyProduct] = []
    seen_product_ids: set[str] = set()
    for page in range(1, max_catalog_pages + 1):
        response_url = f"{_catalog_path(candidate)}?limit={_CATALOG_PAGE_SIZE}&page={page}"
        payload = _fetch_json(candidate, response_url, http_get)
        match payload:
            case ShopifyUnsupportedPlatform() | ShopifyHttpFailure() | ShopifySchemaFailure():
                return _collection_fallback_or_failure(candidate, http_get, payload)
            case ShopifyEmptyCatalog() | ShopifyPaginationFailure():
                return payload
            case {"products": list(raw_products)}:
                if not raw_products:
                    if not products:
                        return ShopifyEmptyCatalog(url=response_url)
                    return _success(candidate, tuple(products))
                page_products = tuple(parse_product(raw_product, _localized_path(candidate)) for raw_product in raw_products)
                if any(product is None for product in page_products):
                    return _collection_fallback_or_failure(
                        candidate,
                        http_get,
                        _schema_failure(candidate, response_url, "Catalog response has an invalid product schema"),
                    )
                added = 0
                for product in page_products:
                    if product is not None and product.product_id not in seen_product_ids:
                        seen_product_ids.add(product.product_id)
                        products.append(product)
                        added += 1
                if added == 0:
                    return ShopifyPaginationFailure(url=response_url, detail="Catalog page repeated only known products")
            case _:
                return _collection_fallback_or_failure(
                    candidate,
                    http_get,
                    _schema_failure(candidate, response_url, "Catalog response is missing a products list"),
                )
    return ShopifyPaginationFailure(url=candidate.origin, detail="Catalog page limit reached before termination")


def _collection_fallback_or_failure(
    candidate: _ShopifyUrl,
    http_get: ShopifyHttpGet,
    failure: ShopifyRetrievalFailure,
) -> ShopifyRetrievalResult:
    match candidate.source:
        case ShopifyRetrievalSource.COLLECTION:
            return _retrieve_collection_html(candidate, http_get)
        case ShopifyRetrievalSource.CATALOG:
            return failure
        case ShopifyRetrievalSource.PRODUCT:
            raise AssertionError("Catalog retrieval received a product target")


def _retrieve_collection_html(candidate: _ShopifyUrl, http_get: ShopifyHttpGet) -> ShopifyRetrievalResult:
    collection_url = f"{_localized_path(candidate)}/collections/{candidate.collection_handle}"
    handles: list[str] = []
    seen_pages: set[str] = set()
    seen_handles: set[str] = set()
    page_url = collection_url
    for _ in range(_MAX_COLLECTION_HTML_PAGES):
        if page_url in seen_pages:
            return ShopifyPaginationFailure(url=page_url, detail="Collection HTML pagination repeated a page")
        seen_pages.add(page_url)
        html = _fetch_html(page_url, http_get)
        match html:
            case ShopifyHttpFailure():
                return html
            case str() as text:
                if not text.strip():
                    return ShopifyEmptyCatalog(url=page_url)
                parsed_page = extract_collection_html_page(text, page_url, collection_url)
                if not parsed_page.product_handles:
                    return _schema_failure(candidate, page_url, "Collection HTML did not contain product links")
                for handle in parsed_page.product_handles:
                    if handle not in seen_handles:
                        seen_handles.add(handle)
                        handles.append(handle)
                match parsed_page.next_page_url:
                    case None:
                        return _retrieve_collection_products(candidate, tuple(handles), http_get)
                    case str() as next_page_url:
                        page_url = next_page_url
    return ShopifyPaginationFailure(url=collection_url, detail="Collection HTML page limit reached before termination")


def _retrieve_collection_products(
    candidate: _ShopifyUrl,
    handles: tuple[str, ...],
    http_get: ShopifyHttpGet,
) -> ShopifyRetrievalResult:
    products: list[ShopifyProduct] = []
    seen_product_ids: set[str] = set()
    for handle in handles:
        result = _retrieve_product_handle(candidate, handle, http_get)
        match result:
            case ShopifyCatalogSuccess(products=(product,)):
                if product.product_id not in seen_product_ids:
                    seen_product_ids.add(product.product_id)
                    products.append(product)
            case ShopifyCatalogSuccess():
                return _schema_failure(candidate, candidate.origin, "Product endpoint returned an unexpected result")
            case ShopifyUnsupportedPlatform() | ShopifyHttpFailure() | ShopifySchemaFailure():
                return result
            case ShopifyEmptyCatalog() | ShopifyPaginationFailure():
                return result
    if not products:
        return ShopifyEmptyCatalog(url=candidate.origin)
    return _success(candidate, tuple(products))


def _fetch_json(
    candidate: _ShopifyUrl,
    response_url: str,
    http_get: ShopifyHttpGet,
) -> JsonValue | ShopifyRetrievalFailure:
    try:
        response = http_get(response_url, timeout=_REQUEST_TIMEOUT_SECONDS)
        if not 200 <= response.status_code < 300:
            return ShopifyHttpFailure(url=response_url, status_code=response.status_code, detail="Unexpected HTTP status")
        return response.json()
    except (JSONDecodeError, RequestsJSONDecodeError):
        return _schema_failure(candidate, response_url, "Response did not contain valid JSON")
    except requests.RequestException as error:
        return ShopifyHttpFailure(url=response_url, status_code=None, detail=type(error).__name__)


def _fetch_html(response_url: str, http_get: ShopifyHttpGet) -> str | ShopifyHttpFailure:
    try:
        response = http_get(response_url, timeout=_REQUEST_TIMEOUT_SECONDS)
        if not 200 <= response.status_code < 300:
            return ShopifyHttpFailure(url=response_url, status_code=response.status_code, detail="Unexpected HTTP status")
        return response.text
    except requests.RequestException as error:
        return ShopifyHttpFailure(url=response_url, status_code=None, detail=type(error).__name__)


def _catalog_path(candidate: _ShopifyUrl) -> str:
    scope = "" if candidate.collection_handle is None else f"/collections/{candidate.collection_handle}"
    return f"{_localized_path(candidate)}{scope}/products.json"


def _localized_path(candidate: _ShopifyUrl) -> str:
    return candidate.origin if candidate.locale is None else f"{candidate.origin}/{candidate.locale}"


def _success(candidate: _ShopifyUrl, products: tuple[ShopifyProduct, ...]) -> ShopifyCatalogSuccess:
    if candidate.source is ShopifyRetrievalSource.PRODUCT and products:
        remember_verified_direct_product_key(candidate.origin, products[0].handle)
    return ShopifyCatalogSuccess(
        origin=candidate.origin,
        source=candidate.source,
        collection_handle=candidate.collection_handle,
        products=products,
    )


def _schema_failure(candidate: _ShopifyUrl, url: str, detail: str) -> ShopifySchemaFailure | ShopifyUnsupportedPlatform:
    if candidate.is_verified_myshopify:
        return ShopifySchemaFailure(url=url, detail=detail)
    return ShopifyUnsupportedPlatform(url=url, detail="Response did not confirm Shopify: " + detail)
