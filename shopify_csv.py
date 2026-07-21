from __future__ import annotations

from typing import Final, TypedDict

import pandas as pd

from scraper_ebay import COLUMNS, MISSING
from shopify_retrieval_types import ShopifyProduct


ShopifyCsvRow = TypedDict(
    "ShopifyCsvRow",
    {
        "Stock": str,
        "URL": str,
        "Make": str,
        "Model": str,
        "Reference Number": str,
        "Year": str,
        "Box": str,
        "Papers": str,
        "Original Price": str,
        "Customized": str,
        "Category": str,
        "Seller": str,
    },
)

SHOPIFY_COLUMNS: Final[pd.Index] = pd.Index(COLUMNS, dtype="object")


def map_shopify_products(products: tuple[ShopifyProduct, ...]) -> pd.DataFrame:
    rows: list[ShopifyCsvRow] = []
    for product in products:
        for variant in product.variants:
            rows.append(
                {
                    "Stock": f"shopify:{product.product_id}:{variant.variant_id}",
                    "URL": product.url,
                    "Make": _text_or_missing(product.vendor),
                    "Model": product.title,
                    "Reference Number": _text_or_missing(variant.sku),
                    "Year": MISSING,
                    "Box": MISSING,
                    "Papers": MISSING,
                    "Original Price": _text_or_missing(variant.price),
                    "Customized": MISSING,
                    "Category": MISSING,
                    "Seller": MISSING,
                }
            )
    return pd.DataFrame(rows, columns=SHOPIFY_COLUMNS)


def _text_or_missing(value: str | None) -> str:
    return value or MISSING
