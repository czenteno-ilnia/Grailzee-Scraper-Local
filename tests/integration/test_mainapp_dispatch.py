from __future__ import annotations

import pandas as pd
import pytest

try:
    import tkinter  # noqa: F401
except ImportError:
    pytest.skip("Tkinter is not available in this Python environment", allow_module_level=True)

import MainApp


@pytest.mark.integration
def test_run_scraper_when_supported_brand_url_is_dispatched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    app = MainApp.MainApp.__new__(MainApp.MainApp)
    logs: list[str] = []
    app.log_scraper = logs.append

    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(MainApp.settings, "report_dir", "reportes")
    monkeypatch.setitem(MainApp.settings, "prefix", "test")
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

    app.run_scraper(["https://www.grandcaliber.com/products/test-watch"])

    assert (tmp_path / "reportes" / "test_scraper.csv").exists()
    assert "✔ OK" in logs


@pytest.mark.integration
def test_run_scraper_when_url_is_unsupported_does_not_write_report(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = MainApp.MainApp.__new__(MainApp.MainApp)
    logs: list[str] = []
    app.log_scraper = logs.append

    monkeypatch.chdir(tmp_path)

    app.run_scraper(["https://unsupported.example/watch"])

    assert not (tmp_path / "reportes").exists()
    assert "⚠️ Sitio no reconocido\n" in logs
