from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeAlias


JsonValue: TypeAlias = "None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]"


class ShopifyRetrievalSource(str, Enum):
    CATALOG = "catalog"
    COLLECTION = "collection"
    PRODUCT = "product"


@dataclass(frozen=True, slots=True)
class ShopifyVariant:
    variant_id: str
    sku: str | None
    price: str | None


@dataclass(frozen=True, slots=True)
class ShopifyProduct:
    product_id: str
    handle: str
    title: str
    vendor: str | None
    variants: tuple[ShopifyVariant, ...]
    url: str


@dataclass(frozen=True, slots=True)
class ShopifyCatalogSuccess:
    origin: str
    source: ShopifyRetrievalSource
    collection_handle: str | None
    products: tuple[ShopifyProduct, ...]

    @property
    def is_direct_product(self) -> bool:
        return self.source is ShopifyRetrievalSource.PRODUCT


@dataclass(frozen=True, slots=True)
class ShopifyUnsupportedPlatform:
    url: str
    detail: str


@dataclass(frozen=True, slots=True)
class ShopifyHttpFailure:
    url: str
    status_code: int | None
    detail: str


@dataclass(frozen=True, slots=True)
class ShopifySchemaFailure:
    url: str
    detail: str


@dataclass(frozen=True, slots=True)
class ShopifyEmptyCatalog:
    url: str


@dataclass(frozen=True, slots=True)
class ShopifyPaginationFailure:
    url: str
    detail: str


ShopifyRetrievalFailure: TypeAlias = (
    ShopifyUnsupportedPlatform
    | ShopifyHttpFailure
    | ShopifySchemaFailure
    | ShopifyEmptyCatalog
    | ShopifyPaginationFailure
)
ShopifyRetrievalResult: TypeAlias = ShopifyCatalogSuccess | ShopifyRetrievalFailure


class ShopifyHttpResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> JsonValue: ...


class ShopifyHttpGet(Protocol):
    def __call__(self, url: str, *, timeout: float) -> ShopifyHttpResponse: ...
