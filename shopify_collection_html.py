from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


@dataclass(frozen=True, slots=True)
class CollectionHtmlPage:
    product_handles: tuple[str, ...]
    next_page_url: str | None


def extract_collection_html_page(html: str, page_url: str, collection_url: str) -> CollectionHtmlPage:
    soup = BeautifulSoup(html, "html.parser")
    handles: list[str] = []
    seen_handles: set[str] = set()
    for link in soup.select("a[href]"):
        match link.get("href"):
            case str() as href:
                handle = _product_handle(urljoin(page_url, href), collection_url)
                if handle is not None and handle not in seen_handles:
                    seen_handles.add(handle)
                    handles.append(handle)
            case _:
                continue
    next_link = soup.select_one("a[rel~='next'][href]")
    next_page_url = None
    if next_link is not None:
        match next_link.get("href"):
            case str() as href:
                candidate = urljoin(page_url, href)
                if _is_collection_page(candidate, collection_url):
                    next_page_url = candidate
            case _:
                pass
    return CollectionHtmlPage(product_handles=tuple(handles), next_page_url=next_page_url)


def _product_handle(url: str, collection_url: str) -> str | None:
    candidate = urlsplit(url)
    collection = urlsplit(collection_url)
    if candidate.scheme != collection.scheme or candidate.netloc != collection.netloc:
        return None
    collection_path = collection.path.rstrip("/")
    locale_path = collection_path.split("/collections/", maxsplit=1)[0]
    paths = ("/products/", f"{locale_path}/products/", f"{collection_path}/products/")
    for prefix in paths:
        if candidate.path.startswith(prefix):
            handle = candidate.path.removeprefix(prefix)
            if handle and "/" not in handle:
                return handle
    return None


def _is_collection_page(url: str, collection_url: str) -> bool:
    candidate = urlsplit(url)
    collection = urlsplit(collection_url)
    return (
        candidate.scheme == collection.scheme
        and candidate.netloc == collection.netloc
        and candidate.path.rstrip("/") == collection.path.rstrip("/")
    )
