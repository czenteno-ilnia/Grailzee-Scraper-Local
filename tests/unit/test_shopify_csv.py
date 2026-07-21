from __future__ import annotations

import pytest

from scraper_ebay import COLUMNS, MISSING
from shopify_csv import map_shopify_products
from shopify_retrieval_types import ShopifyProduct, ShopifyVariant


@pytest.mark.unit
def test_map_shopify_products_when_product_has_multiple_variants_returns_one_ordered_row_per_variant() -> None:
    product = ShopifyProduct(
        product_id="product-42",
        handle="speedmaster-professional",
        title="Speedmaster Professional",
        vendor="Omega",
        variants=(
            ShopifyVariant(variant_id="variant-1", sku="310.30.42.50.01.001", price="7200.00"),
            ShopifyVariant(variant_id="variant-2", sku="310.32.42.50.01.002", price="7350.00"),
        ),
        url="https://dealer.myshopify.com/products/speedmaster-professional",
    )

    dataframe = map_shopify_products((product,))

    assert list(dataframe.columns) == COLUMNS
    assert dataframe.to_dict(orient="records") == [
        {
            "Stock": "shopify:product-42:variant-1",
            "URL": "https://dealer.myshopify.com/products/speedmaster-professional",
            "Make": "Omega",
            "Model": "Speedmaster Professional",
            "Reference Number": "310.30.42.50.01.001",
            "Year": MISSING,
            "Box": MISSING,
            "Papers": MISSING,
            "Original Price": "7200.00",
            "Customized": MISSING,
            "Category": MISSING,
            "Seller": MISSING,
        },
        {
            "Stock": "shopify:product-42:variant-2",
            "URL": "https://dealer.myshopify.com/products/speedmaster-professional",
            "Make": "Omega",
            "Model": "Speedmaster Professional",
            "Reference Number": "310.32.42.50.01.002",
            "Year": MISSING,
            "Box": MISSING,
            "Papers": MISSING,
            "Original Price": "7350.00",
            "Customized": MISSING,
            "Category": MISSING,
            "Seller": MISSING,
        },
    ]


@pytest.mark.unit
def test_map_shopify_products_when_product_has_no_variants_returns_empty_exact_schema() -> None:
    product = ShopifyProduct(
        product_id="product-42",
        handle="speedmaster-professional",
        title="Speedmaster Professional",
        vendor="Omega",
        variants=(),
        url="https://dealer.myshopify.com/products/speedmaster-professional",
    )

    dataframe = map_shopify_products((product,))

    assert list(dataframe.columns) == COLUMNS
    assert dataframe.empty


@pytest.mark.unit
def test_map_shopify_products_when_optional_variant_and_vendor_values_are_missing_uses_missing_literal() -> None:
    product = ShopifyProduct(
        product_id="product-42",
        handle="speedmaster-professional",
        title="Speedmaster Professional",
        vendor=None,
        variants=(ShopifyVariant(variant_id="variant-1", sku=None, price=None),),
        url="https://dealer.myshopify.com/products/speedmaster-professional",
    )

    dataframe = map_shopify_products((product,))

    assert dataframe.iloc[0].to_dict() == {
        "Stock": "shopify:product-42:variant-1",
        "URL": "https://dealer.myshopify.com/products/speedmaster-professional",
        "Make": MISSING,
        "Model": "Speedmaster Professional",
        "Reference Number": MISSING,
        "Year": MISSING,
        "Box": MISSING,
        "Papers": MISSING,
        "Original Price": MISSING,
        "Customized": MISSING,
        "Category": MISSING,
        "Seller": MISSING,
    }
