from __future__ import annotations

from collections.abc import Callable
from typing_extensions import assert_never

import pandas as pd

from shopify_csv import map_shopify_products
from shopify_retrieval_types import (
    ShopifyCatalogSuccess,
    ShopifyEmptyCatalog,
    ShopifyHttpFailure,
    ShopifyPaginationFailure,
    ShopifyRetrievalResult,
    ShopifySchemaFailure,
    ShopifyUnsupportedPlatform,
)
from shopify_url import _parse_shopify_url

ShopifyRetriever = Callable[[str], ShopifyRetrievalResult]
Log = Callable[[str], None]


def is_shopify_url_candidate(url: str) -> bool:
    return _parse_shopify_url(url, require_myshopify=False) is not None


def retrieve_shopify_rows(url: str, *, retrieve_products: ShopifyRetriever, log: Log) -> pd.DataFrame | None:
    match retrieve_products(url):
        case ShopifyCatalogSuccess(products=products):
            return map_shopify_products(products)
        case ShopifyUnsupportedPlatform(detail=detail) | ShopifyHttpFailure(detail=detail) | ShopifySchemaFailure(detail=detail) | ShopifyPaginationFailure(detail=detail):
            log(f"   ⚠️ Shopify: {detail}")
        case ShopifyEmptyCatalog():
            log("   ⚠️ Shopify: catálogo sin productos")
        case unreachable:
            assert_never(unreachable)
    return None
