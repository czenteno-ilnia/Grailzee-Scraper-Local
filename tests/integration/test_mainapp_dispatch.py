from __future__ import annotations

import pandas as pd
import pytest

try:
    import tkinter  # noqa: F401
except ImportError:
    pytest.skip("Tkinter is not available in this Python environment", allow_module_level=True)

import MainApp


@pytest.mark.integration
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.ebay.com/itm/123", True),
        ("http://chrono24.com/watch", True),
        ("str-item-card__link href", False),
        ("ebay.com/itm/123", False),
    ],
)
def test_is_valid_url(value: str, expected: bool) -> None:
    assert MainApp.is_valid_url(value) is expected


@pytest.mark.integration
def test_run_scraper_when_supported_brand_url_is_dispatched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.log = lambda msg: None
    monkeypatch.setattr(
        MainApp.scraper_chrono24,
        "scrape_multiple",
        lambda urls, existing_ids=None, progress_callback=None: pd.DataFrame([{
            "Stock": "1",
            "URL": urls[0],
            "Make": "Rolex",
            "Model": "Datejust",
            "Reference Number": "Ref",
            "Year": "2024",
            "Box": "Yes",
            "Papers": "Yes",
            "Original Price": "$1",
        }]),
    )

    df = app._dispatch("https://www.chrono24.com/search/index.htm?customerId=23766&dosearch=true")

    assert df is not None
    assert df.iloc[0]["Make"] == "Rolex"


@pytest.mark.integration
def test_run_scraper_when_url_is_unsupported_does_not_write_report(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    logs: list[str] = []
    app.log = logs.append

    df = app._dispatch("https://unsupported.example/watch")

    assert df is None
    assert logs == ["   ⚠️ Sitio no reconocido"]


class FakeEntry:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value


@pytest.mark.integration
def test_batch_csv_path_uses_report_name_and_slugifies(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("Rolex Batch #3")
    monkeypatch.setitem(MainApp.settings, "report_dir", "reportes")

    assert app._batch_csv_path() == "reportes/Rolex_Batch_3.csv"


@pytest.mark.integration
def test_batch_csv_path_defaults_to_timestamp_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("")
    monkeypatch.setitem(MainApp.settings, "report_dir", "reportes")

    csv_path = app._batch_csv_path()
    name = csv_path.split("/")[-1]
    assert name.startswith("batch_") and name.endswith(".csv")


@pytest.mark.integration
def test_run_scraper_retries_a_failed_url_once(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    app.entry_report_name = FakeEntry("failed")
    app.entry_oxy_user = FakeEntry()
    app.entry_oxy_pass = FakeEntry()
    app.progress = {}
    logs: list[str] = []
    app.log = logs.append
    app._set_status = lambda status: None
    app._update_latest_info = lambda: None
    calls: list[str] = []
    app._dispatch = lambda url, **kwargs: calls.append(url)
    monkeypatch.setitem(MainApp.settings, "report_dir", str(tmp_path))
    monkeypatch.setattr(MainApp.dd, "known_ids", lambda: set())

    app._run_scraper(["https://www.ebay.com/itm/123"], ["str-item-card__link href"])

    assert calls == ["https://www.ebay.com/itm/123"] * 2
    assert len(pd.read_csv(tmp_path / "failed.csv")) == 1
    assert logs[-1] == "   • str-item-card__link href"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("url", "known_ids", "expected"),
    [
        ("https://www.ebay.com/itm/123456?hash=abc", {"123456"}, "123456"),
        (
            "https://www.chrono24.com/rolex/datejust--id987654.htm?SETLANG=en_US",
            {"https://www.chrono24.com/rolex/datejust--id987654.htm"},
            "https://www.chrono24.com/rolex/datejust--id987654.htm",
        ),
        ("https://www.ebay.com/sch/i.html?_nkw=omega", {"123456"}, None),
        (
            "https://www.chrono24.com/search/index.htm?customerId=23766",
            {"https://www.chrono24.com/rolex/datejust--id987654.htm"},
            None,
        ),
    ],
)
def test_known_single_item_key_only_matches_direct_items(url, known_ids, expected) -> None:
    assert MainApp.known_single_item_key(url, known_ids) == expected


@pytest.mark.integration
def test_localize_first_seen_for_mexico_csv() -> None:
    df = pd.DataFrame({"first_seen": ["2026-07-17T14:37:00Z", "2026-07-16T08:48:50", ""]})

    result = MainApp.localize_first_seen(df)

    assert result["first_seen"].tolist() == [
        "2026-07-17 08:37:00 -0600",
        "2026-07-16 08:48:50 -0600",
        "",
    ]
