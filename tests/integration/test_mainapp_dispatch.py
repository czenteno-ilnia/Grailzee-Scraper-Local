from __future__ import annotations

import pandas as pd
import pytest

try:
    import tkinter  # noqa: F401
except ImportError:
    pytest.skip("Tkinter is not available in this Python environment", allow_module_level=True)

import MainApp


class FakeCombo:
    def __init__(self, values: list[str], selected: str = "") -> None:
        self.values = values
        self.selected = selected

    def __getitem__(self, key: str):
        if key == "values":
            return self.values
        raise KeyError(key)

    def get(self) -> str:
        return self.selected

    def set(self, value: str) -> None:
        self.selected = value


@pytest.mark.integration
def test_run_scraper_when_supported_brand_url_is_dispatched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    monkeypatch.setattr(
        MainApp.Scraper_Grandcaliber,
        "scrape_url",
        lambda url: pd.DataFrame([{
            "Stock": "1",
            "URL": url,
            "Make": "Grand Caliber",
            "Model": "Model",
            "Reference Number": "Ref",
            "Year": "2024",
            "Box": "Yes",
            "Papers": "Yes",
            "Original Price": "$1",
        }]),
    )

    df = app._dispatch("https://www.grandcaliber.com/products/test-watch")

    assert df is not None
    assert df.iloc[0]["Make"] == "Grand Caliber"


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
