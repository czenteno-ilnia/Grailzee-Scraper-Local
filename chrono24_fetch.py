from __future__ import annotations

import os
import time

from bs4 import BeautifulSoup
import requests

PAGE_TIMEOUT_SECONDS = 20
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_UNDETECTED_CHROME_DISABLED = False


def _is_blocked_html(html: str) -> bool:
    lowered = html.lower()
    return any(token in lowered for token in ("captcha", "access denied", "blocked", "robot"))


def get_soup_with_requests(url: str) -> BeautifulSoup | None:
    try:
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=PAGE_TIMEOUT_SECONDS)
    except requests.RequestException:
        return None

    if response.status_code != 200 or _is_blocked_html(response.text):
        return None

    return BeautifulSoup(response.text, "html.parser")


def get_soup_with_browser(url: str) -> BeautifulSoup:
    global _UNDETECTED_CHROME_DISABLED
    from selenium.common.exceptions import WebDriverException

    if not _UNDETECTED_CHROME_DISABLED:
        try:
            return _get_soup_with_undetected_chrome(url)
        except (ImportError, OSError, RuntimeError, WebDriverException) as exc:
            _UNDETECTED_CHROME_DISABLED = True
            print(f"undetected Chrome failed, using regular Selenium Chrome: {exc}")

    driver = make_selenium_driver()
    try:
        return soup_from_driver(driver, url)
    finally:
        driver.quit()


def _get_soup_with_undetected_chrome(url: str) -> BeautifulSoup:
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument("--lang=en-US")
    if os.environ.get("CHRONO24_HEADLESS") == "1":
        options.add_argument("--headless=new")

    driver = uc.Chrome(options=options)
    try:
        return soup_from_driver(driver, url)
    finally:
        driver.quit()


def make_selenium_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=en-US")
    options.add_argument(f"--user-agent={BROWSER_HEADERS['User-Agent']}")

    return webdriver.Chrome(options=options)


def soup_from_driver(driver, url: str) -> BeautifulSoup:
    driver.get(url)
    for _ in range(40):
        html = driver.page_source
        if "--id" in html or "Listing code" in html or "Listing ID" in html:
            break
        time.sleep(0.5)
    return BeautifulSoup(driver.page_source, "html.parser")
