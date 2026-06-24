from __future__ import annotations

import builtins
import os
import sys
from pathlib import Path
from typing import Callable

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
SECRET_FILENAMES = frozenset({
    "credentials.json",
    "ebay_token.json",
    "ebay_api_credentials.txt",
})

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def _is_secret_path(path: str | os.PathLike[str]) -> bool:
    return Path(path).name in SECRET_FILENAMES


@pytest.fixture(autouse=True)
def block_real_secret_files(monkeypatch: pytest.MonkeyPatch) -> None:
    original_open: Callable[..., object] = builtins.open
    original_path_open = Path.open

    def guarded_open(file: str | os.PathLike[str], *args: object, **kwargs: object) -> object:
        if _is_secret_path(file):
            raise AssertionError(f"Tests must not open real secret file: {file}")
        return original_open(file, *args, **kwargs)

    def guarded_path_open(self: Path, *args: object, **kwargs: object) -> object:
        if _is_secret_path(self):
            raise AssertionError(f"Tests must not open real secret file: {self}")
        return original_path_open(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(Path, "open", guarded_path_open)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_browser = os.environ.get("RUN_BROWSER_TESTS") == "1"
    run_ui = os.environ.get("RUN_UI_TESTS") == "1"
    has_display = os.name == "nt" or bool(os.environ.get("DISPLAY"))

    browser_skip = pytest.mark.skip(reason="Set RUN_BROWSER_TESTS=1 to run browser tests")
    ui_skip = pytest.mark.skip(reason="Set RUN_UI_TESTS=1 or run with a display to run UI tests")

    for item in items:
        keywords = item.keywords
        if "browser" in keywords and not run_browser:
            item.add_marker(browser_skip)
        if "ui" in keywords and not (run_ui or has_display):
            item.add_marker(ui_skip)
