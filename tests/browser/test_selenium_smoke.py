from __future__ import annotations

import pytest


@pytest.mark.browser
def test_selenium_can_import_webdriver() -> None:
    from selenium import webdriver

    assert webdriver.ChromeOptions is not None
