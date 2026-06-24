from __future__ import annotations

from dataclasses import dataclass

import pytest

import google_loader


@dataclass(frozen=True, slots=True)
class FakeCredentials:
    path: str


@dataclass(frozen=True, slots=True)
class FakeSpreadsheet:
    url: str


@dataclass(frozen=True, slots=True)
class FakeClient:
    def open_by_url(self, sheet_url: str) -> FakeSpreadsheet:
        return FakeSpreadsheet(sheet_url)


@pytest.mark.api
@pytest.mark.integration
def test_connect_to_spreadsheet_when_google_clients_are_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_service_account_file(path: str, scopes: list[str]) -> FakeCredentials:
        assert path == "fake-service-account.json"
        assert scopes == ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        return FakeCredentials(path)

    def fake_authorize(credentials: FakeCredentials) -> FakeClient:
        assert credentials.path == "fake-service-account.json"
        return FakeClient()

    monkeypatch.setattr(
        google_loader.Credentials,
        "from_service_account_file",
        fake_from_service_account_file,
    )
    monkeypatch.setattr(google_loader.gspread, "authorize", fake_authorize)

    spreadsheet = google_loader.connect_to_spreadsheet(
        "https://docs.google.com/spreadsheets/d/fake-id",
        creds_path="fake-service-account.json",
    )

    assert spreadsheet.url == "https://docs.google.com/spreadsheets/d/fake-id"
