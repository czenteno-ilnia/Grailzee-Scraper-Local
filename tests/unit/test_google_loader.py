from __future__ import annotations

import pandas as pd
import pytest

from google_loader import extract_ebay_links, get_customer_url, load_customers_dict, normalize_name


@pytest.mark.unit
def test_extract_ebay_links_when_cells_contain_urls() -> None:
    df = pd.DataFrame({
        "notes": [
            "watch https://www.ebay.com/itm/1234567890?hash=abc",
            "duplicate https://www.ebay.com/itm/1234567890?hash=other",
            "ignore https://example.com/itm/555",
        ],
        "other": ["", "https://www.ebay.com/itm/999#frag", None],
    })

    links = set(extract_ebay_links(df))

    assert links == {
        "https://www.ebay.com/itm/1234567890",
        "https://www.ebay.com/itm/999",
    }


@pytest.mark.unit
def test_normalize_name_when_value_has_accents_and_symbols() -> None:
    assert normalize_name("  José's Watch-Co.  ") == "jose s watch co"


@pytest.mark.unit
def test_load_customers_dict_when_required_columns_exist() -> None:
    df = pd.DataFrame({
        "Account": ["Alpha Watches", ""],
        "Link to site": ["https://example.com/alpha", "https://example.com/empty"],
        "Ignored": ["x", "y"],
    })

    customers = load_customers_dict(df)

    assert customers == {"Alpha Watches": "https://example.com/alpha"}


@pytest.mark.unit
def test_get_customer_url_when_name_matches_partially() -> None:
    customers = {"Alpha Luxury Watches": "https://example.com/alpha"}

    assert get_customer_url("alpha", customers) == "https://example.com/alpha"


@pytest.mark.unit
def test_get_customer_url_when_dictionary_is_empty() -> None:
    assert get_customer_url("alpha", {}) is None
