import re

import pandas as pd
import pytest

import dedupe


SHOPIFY_TEST_TABLE_ENV = "GRAILZEE_DEDUPE_TABLE"


def assert_uses_only_shopify_test_table(statements):
    sql_statements = [statement["sql"] for statement in statements]
    assert all("seen_shopify_test" in sql for sql in sql_statements)
    assert not any(re.search(r"(?<!\w)seen(?!\w)", sql) for sql in sql_statements)


def test_record_df_uses_turso_utc_timestamp(monkeypatch):
    captured = []

    def fake_execute(statements):
        captured.extend(statements)
        result = {"response": {"result": {"affected_row_count": 1}}}
        return [result for _ in statements]

    monkeypatch.setattr(dedupe, "_execute", fake_execute)
    row = {column: "value" for column in dedupe.COLUMNS}
    row.update({"Stock": "123", "URL": "https://www.ebay.com/itm/123"})

    assert dedupe.record_df(pd.DataFrame([row])) == 1
    assert "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')" in captured[1]["sql"]
    assert len(captured[1]["args"]) == 13


def test_distinct_sellers(monkeypatch):
    captured = []

    def fake_execute(statements):
        captured.extend(statements)
        rows = [[{"type": "text", "value": "WatchGuys"}], [{"type": "text", "value": "luxwatch"}]]
        return [{"response": {"result": {"rows": rows}}}]

    monkeypatch.setattr(dedupe, "_execute", fake_execute)
    assert dedupe.distinct_sellers() == ["WatchGuys", "luxwatch"]
    assert "SELECT DISTINCT seller" in captured[0]["sql"]
    assert "seller != ''" in captured[0]["sql"]


def test_fetch_by_seller(monkeypatch):
    captured = []
    row = [{"type": "text", "value": f"v{i}"} for i in range(13)] + [{"type": "null", "value": None}]

    def fake_execute(statements):
        captured.extend(statements)
        return [{"response": {"result": {"rows": [row]}}}]

    monkeypatch.setattr(dedupe, "_execute", fake_execute)
    df = dedupe.fetch_by_seller("WatchGuys")

    assert "SELECT *" not in captured[0]["sql"]
    assert captured[0]["args"] == [{"type": "text", "value": "WatchGuys"}]
    assert "first_seen DESC" in captured[0]["sql"]
    assert "first_seen IS NULL" in captured[0]["sql"]
    assert list(df.columns) == dedupe.COLUMNS + ["Source", "first_seen"]
    assert df.iloc[0]["Stock"] == "v0"
    assert df.iloc[0]["Source"] == "v12"
    assert df.iloc[0]["first_seen"] == ""


def test_fetch_all(monkeypatch):
    captured = []

    def fake_execute(statements):
        captured.extend(statements)
        return [{"response": {"result": {"rows": []}}}]

    monkeypatch.setattr(dedupe, "_execute", fake_execute)
    df = dedupe.fetch_all()
    assert "WHERE" not in captured[0]["sql"]
    assert captured[0]["args"] == []
    assert list(df.columns) == dedupe.COLUMNS + ["Source", "first_seen"]


def test_fetch_by_seller_empty(monkeypatch):
    monkeypatch.setattr(dedupe, "_execute", lambda s: [{"response": {"result": {"rows": []}}}])
    df = dedupe.fetch_by_seller("nobody")
    assert df.empty
    assert list(df.columns) == dedupe.COLUMNS + ["Source", "first_seen"]


def test_source_from_url_detects_shopify_myshopify_and_verified_stock_ids():
    assert dedupe._source_from_url("https://dealer.myshopify.com/products/watch") == "Shopify"
    assert dedupe._source_from_url(
        "https://dealer.example/products/watch", "shopify:product-42:variant-7"
    ) == "Shopify"


def test_known_ids_qualifies_equal_stock_ids_by_source(monkeypatch):
    rows = [
        [
            {"type": "text", "value": "ebay"},
            {"type": "text", "value": "shared-stock"},
            {"type": "text", "value": "https://www.ebay.com/itm/shared-stock"},
        ],
        [
            {"type": "text", "value": "other"},
            {"type": "text", "value": "shopify:product-42:variant-7"},
            {"type": "text", "value": "https://dealer.example/products/watch"},
        ],
    ]

    def fake_execute(statements):
        return [
            {"response": {"result": {}}},
            {"response": {"result": {"rows": rows}}},
        ]

    monkeypatch.setattr(dedupe, "_execute", fake_execute)

    assert dedupe.known_ids() == {
        ("ebay", "shared-stock"),
        ("ebay", "https://www.ebay.com/itm/shared-stock"),
        ("Shopify", "shopify:product-42:variant-7"),
        ("Shopify", "https://dealer.example/products/watch"),
    }


def test_record_df_persists_verified_custom_shopify_rows_as_shopify(monkeypatch):
    captured = []

    def fake_execute(statements):
        captured.extend(statements)
        return [{"response": {"result": {"affected_row_count": 1}}} for _ in statements]

    monkeypatch.setattr(dedupe, "_execute", fake_execute)
    row = {column: "value" for column in dedupe.COLUMNS}
    row.update({
        "Stock": "shopify:product-42:variant-7",
        "URL": "https://dealer.example/products/watch",
    })

    assert dedupe.record_df(pd.DataFrame([row])) == 1
    assert captured[1]["args"][0]["value"] == "Shopify"


def test_known_ids_creates_and_queries_only_the_shopify_test_table(monkeypatch):
    captured = []

    def fake_execute(statements):
        captured.extend(statements)
        return [
            {"response": {"result": {}}},
            {"response": {"result": {"rows": []}}},
        ]

    monkeypatch.setenv(SHOPIFY_TEST_TABLE_ENV, "seen_shopify_test")
    monkeypatch.setattr(dedupe, "_execute", fake_execute)

    assert dedupe.known_ids() == set()

    assert_uses_only_shopify_test_table(captured)
    assert captured[0]["sql"].startswith("CREATE TABLE IF NOT EXISTS seen_shopify_test")
    assert "SELECT source, stock_id, url FROM seen_shopify_test" in captured[1]["sql"]


def test_record_df_creates_and_records_only_the_shopify_test_table(monkeypatch):
    captured = []

    def fake_execute(statements):
        captured.extend(statements)
        result = {"response": {"result": {"affected_row_count": 1}}}
        return [result for _ in statements]

    row = {column: "value" for column in dedupe.COLUMNS}
    row.update({"Stock": "shopify:product-42:variant-7", "URL": "https://dealer.example/products/watch"})
    monkeypatch.setenv(SHOPIFY_TEST_TABLE_ENV, "seen_shopify_test")
    monkeypatch.setattr(dedupe, "_execute", fake_execute)

    assert dedupe.record_df(pd.DataFrame([row])) == 1

    assert_uses_only_shopify_test_table(captured)
    assert "INSERT OR IGNORE INTO seen_shopify_test" in captured[1]["sql"]


def test_fetch_all_queries_only_the_shopify_test_table(monkeypatch):
    captured = []

    def fake_execute(statements):
        captured.extend(statements)
        return [{"response": {"result": {"rows": []}}}]

    monkeypatch.setenv(SHOPIFY_TEST_TABLE_ENV, "seen_shopify_test")
    monkeypatch.setattr(dedupe, "_execute", fake_execute)

    assert dedupe.fetch_all().empty

    assert_uses_only_shopify_test_table(captured)


def test_distinct_sellers_queries_only_the_shopify_test_table(monkeypatch):
    captured = []

    def fake_execute(statements):
        captured.extend(statements)
        return [{"response": {"result": {"rows": []}}}]

    monkeypatch.setenv(SHOPIFY_TEST_TABLE_ENV, "seen_shopify_test")
    monkeypatch.setattr(dedupe, "_execute", fake_execute)

    assert dedupe.distinct_sellers() == []

    assert_uses_only_shopify_test_table(captured)


def test_fetch_rows_queries_only_the_shopify_test_table(monkeypatch):
    captured = []

    def fake_execute(statements):
        captured.extend(statements)
        return [{"response": {"result": {"rows": []}}}]

    monkeypatch.setenv(SHOPIFY_TEST_TABLE_ENV, "seen_shopify_test")
    monkeypatch.setattr(dedupe, "_execute", fake_execute)

    assert dedupe.fetch_rows(["shopify:product-42:variant-7"]).empty

    assert_uses_only_shopify_test_table(captured)


def test_dedupe_table_selector_allows_only_known_table_names(monkeypatch):
    monkeypatch.delenv(SHOPIFY_TEST_TABLE_ENV, raising=False)
    assert dedupe._dedupe_table() == "seen"

    monkeypatch.setenv(SHOPIFY_TEST_TABLE_ENV, "seen_shopify_test")
    assert dedupe._dedupe_table() == "seen_shopify_test"

    monkeypatch.setenv(SHOPIFY_TEST_TABLE_ENV, "seen; DROP TABLE seen")
    with pytest.raises(ValueError):
        dedupe._dedupe_table()
