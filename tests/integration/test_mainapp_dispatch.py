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


@pytest.mark.integration
def test_auto_detect_csv_when_chrono24_has_customer_id_ignores_selected_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    app = MainApp.GrailzeeApp.__new__(MainApp.GrailzeeApp)
    logs: list[str] = []
    app.log = logs.append
    app.combo_csv = FakeCombo(["fusionjewelersny.csv"], selected="fusionjewelersny.csv")
    app._on_csv_selected = lambda: None

    monkeypatch.setitem(MainApp.settings, "report_dir", "reportes")

    csv_path = app._auto_detect_csv([
        "https://www.chrono24.com/search/index.htm?customerId=24770&dosearch=true"
    ])

    assert csv_path == "reportes/chrono24_24770.csv"
    assert app.combo_csv.get() == "fusionjewelersny.csv"
    assert logs == ["📂 Nuevo CSV Chrono24: chrono24_24770.csv"]
