from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit

from shopify_retrieval_types import ShopifyRetrievalSource


_VERIFIED_CUSTOM_DIRECT_PRODUCT_KEYS: set[str] = set()


_HOST_LABEL: Final = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)
_LOCALE_PREFIX: Final = re.compile(r"[a-z]{2}(?:-[a-z]{2})?", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ShopifyUrlTarget:
    origin: str
    source: ShopifyRetrievalSource
    locale: str | None
    product_handle: str | None
    collection_handle: str | None
    is_verified_myshopify: bool


def normalize_store_origin(url: str) -> str | None:
    """Return a canonical HTTPS Shopify store origin for supported URL shapes."""
    normalized = _parse_shopify_url(url, require_myshopify=True)
    return normalized.origin if normalized is not None else None


def direct_product_key(url: str) -> str | None:
    """Return a stable canonical key for a direct Shopify product URL."""
    normalized = _parse_shopify_url(url, require_myshopify=False)
    if normalized is None or normalized.product_handle is None:
        return None
    key = f"{normalized.origin}/products/{normalized.product_handle}"
    if normalized.is_verified_myshopify or key in _VERIFIED_CUSTOM_DIRECT_PRODUCT_KEYS:
        return key
    return None


def verified_direct_product_key(url: str) -> str | None:
    normalized = _parse_shopify_url(url, require_myshopify=False)
    if normalized is None or normalized.product_handle is None:
        return None
    return f"{normalized.origin}/products/{normalized.product_handle}"


def remember_verified_direct_product_key(origin: str, product_handle: str) -> None:
    _VERIFIED_CUSTOM_DIRECT_PRODUCT_KEYS.add(f"{origin}/products/{product_handle}")


def _parse_shopify_url(url: str, *, require_myshopify: bool) -> ShopifyUrlTarget | None:
    if not url or any(character.isspace() for character in url):
        return None
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() not in ("http", "https") or parsed.username or parsed.password:
        return None
    if port not in (None, 80, 443):
        return None
    host = (parsed.hostname or "").removesuffix(".").lower()
    is_verified_myshopify = _is_valid_myshopify_host(host)
    if (require_myshopify and not is_verified_myshopify) or not _is_valid_store_host(host):
        return None
    path = parsed.path or "/"
    if "//" in path:
        return None
    segments = tuple(segment for segment in path.split("/") if segment)
    locale = None
    if segments and _LOCALE_PREFIX.fullmatch(segments[0]):
        locale = segments[0].lower()
        segments = segments[1:]
    origin = f"https://{host}"
    if not segments:
        return ShopifyUrlTarget(origin, ShopifyRetrievalSource.CATALOG, locale, None, None, is_verified_myshopify)
    if len(segments) != 2 or not segments[1]:
        return None
    resource, handle = segments
    match resource:
        case "products":
            return ShopifyUrlTarget(origin, ShopifyRetrievalSource.PRODUCT, locale, handle, None, is_verified_myshopify)
        case "collections":
            return ShopifyUrlTarget(origin, ShopifyRetrievalSource.COLLECTION, locale, None, handle, is_verified_myshopify)
        case _:
            return None


def _is_valid_myshopify_host(host: str) -> bool:
    labels = host.split(".")
    return (
        len(host) <= 253
        and len(labels) == 3
        and labels[1:] == ["myshopify", "com"]
        and all(_HOST_LABEL.fullmatch(label) is not None for label in labels)
    )


def _is_valid_store_host(host: str) -> bool:
    labels = host.split(".")
    return (
        len(host) <= 253
        and len(labels) >= 2
        and any(not label.isdecimal() for label in labels)
        and all(_HOST_LABEL.fullmatch(label) is not None for label in labels)
    )
