import pandas as pd

import dedupe


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
