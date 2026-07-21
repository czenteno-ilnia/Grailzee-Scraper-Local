from __future__ import annotations

from shopify_retrieval_types import JsonValue, ShopifyProduct, ShopifyVariant


def parse_product(raw_product: JsonValue, localized_origin: str) -> ShopifyProduct | None:
    match raw_product:
        case {"id": identifier, "handle": str(handle), "title": str(title), **fields} if handle and title:
            product_id = _parse_identifier(identifier)
            variants = _parse_variants(fields.get("variants"))
            if product_id is None or variants is None:
                return None
            return ShopifyProduct(
                product_id=product_id,
                handle=handle,
                title=title,
                vendor=_optional_text(fields.get("vendor")),
                variants=variants,
                url=f"{localized_origin}/products/{handle}",
            )
        case _:
            return None


def _parse_variants(raw_variants: JsonValue | None) -> tuple[ShopifyVariant, ...] | None:
    match raw_variants:
        case None:
            return ()
        case list() as variants:
            parsed_variants: list[ShopifyVariant] = []
            for variant in variants:
                match variant:
                    case {"id": identifier, **fields}:
                        variant_id = _parse_identifier(identifier)
                        if variant_id is None:
                            return None
                        parsed_variants.append(
                            ShopifyVariant(
                                variant_id=variant_id,
                                sku=_optional_text(fields.get("sku")),
                                price=_optional_text(fields.get("price")),
                            )
                        )
                    case _:
                        return None
            return tuple(parsed_variants)
        case _:
            return None


def _parse_identifier(value: JsonValue) -> str | None:
    match value:
        case bool():
            return None
        case int() as identifier if identifier > 0:
            return str(identifier)
        case str() as identifier if identifier:
            return identifier
        case _:
            return None


def _optional_text(value: JsonValue | None) -> str | None:
    match value:
        case str() as text:
            return text
        case _:
            return None
