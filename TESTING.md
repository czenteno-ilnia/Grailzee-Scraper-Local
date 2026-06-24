# Testing The Scraper

This test environment is for the pure scraping work. The default test suite does not require real Google credentials, eBay API credentials, browser automation, API calls, or live network access.

Run all commands from this folder:

```text
App-20260622T164520Z-3-001/App/App
```

## Install On Linux Or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-test.txt
```

## Install On Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-test.txt
```

If PowerShell blocks activation, run this once for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Install On Windows Command Prompt

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-test.txt
```

## Default Test Run

```bash
python -m pytest
```

The default command excludes tests marked `api`, `browser`, `network`, or `credentials`. UI tests are skipped automatically on headless Linux unless a display is available or `RUN_UI_TESTS=1` is set.

## Useful Test Commands

Run fast unit tests:

```bash
python -m pytest -m unit
```

Run pure integration tests:

```bash
python -m pytest -m "integration and not api"
```

Run everything that is safe without credentials or live network:

```bash
python -m pytest -m "not api and not browser and not network and not credentials"
```

Run syntax checks for primary app modules:

```bash
python -m py_compile MainApp.py scraper_ebay.py scraper_chrono24.py scraper_swisstimepiececo.py Scraper_Wywatl.py Scraper_Thewatchoutlet.py Scraper_Grandcaliber.py Scraper_Boknowsluxury.py Scraper_Timepieceperfection.py Nuevos_Clientes.py google_loader.py ebay_auth.py scraper_vendedor.py
```

## Optional UI Smoke Test

Linux needs a display server for Tkinter UI tests. On a desktop session this may work directly:

```bash
RUN_UI_TESTS=1 python -m pytest -m ui
```

On headless Linux, use a virtual display such as `xvfb-run` if available:

```bash
xvfb-run -a python -m pytest -m ui
```

Windows and macOS usually have a display available when run from a normal user session.

If Linux reports that `_tkinter` or `libtk8.6.so` is missing, install the OS Tk package for your Python distribution. Common package names are `python3-tk`, `tk`, or `tk-devel`, depending on the distro.

## Optional Browser Smoke Test

Browser tests are scaffolding for later Selenium checks. They are off by default.

```bash
RUN_BROWSER_TESTS=1 python -m pytest -m browser
```

Chrome or Chromium must be installed before real Selenium browser tests can be added.

## Credential Safety

Default tests must never open these files:

- `credentials.json`
- `ebay_token.json`
- `ebay_api_credentials.txt`

`tests/conftest.py` blocks those filenames during tests. Keep all default tests pure and local. If a future test truly requires credentials or an external API, mark it with `api`, `credentials`, and `network` as appropriate so it stays excluded from normal runs.

## Test Layout

- `tests/unit/`: fast pure helper and parser tests.
- `tests/integration/`: cross-module behavior with local fixtures by default; API-backed scaffolding is marked `api`.
- `tests/ui/`: optional Tkinter startup smoke tests.
- `tests/browser/`: optional Selenium/browser smoke tests.

## Pure Scraping Rule

The current target is pure scraping. New tests should prefer saved HTML fixtures, parser helpers, plain HTML parsing, and local files under pytest `tmp_path`. Do not add Google Sheets, eBay token, external API, or live browser dependencies to the default suite.
