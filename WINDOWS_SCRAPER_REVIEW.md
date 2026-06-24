# Windows Scraper Review

## Scope

Current task: fix the Windows version of the scraper only. Do not expand into the Mac scraper, broad UI changes, credential changes, or unrelated cleanup.

## Source Of Truth

Primary Windows app folder:

```text
App-20260622T164520Z-3-001/App/App
```

Primary launch file:

```text
Run_App.bat
```

Primary application entry point:

```text
MainApp.py
```

Main scraper dispatch currently lives in `MainApp.py` inside `run_scraper()`. It recognizes these URL families:

- eBay: `scraper_ebay.scrape_url(url)`
- Chrono24: `scraper_chrono24.scrape_multiple([url])`
- Swiss Timepiece: `scraper_swisstimepiececo.scrape_url(url)`
- WY WAT L: `Scraper_Wywatl.scrape_url(url)`
- The Watch Outlet: `Scraper_Thewatchoutlet.scrape_url(url)`
- Grand Caliber: `Scraper_Grandcaliber.scrape_url(url)`
- Bo Knows Luxury: `Scraper_Boknowsluxury.scrape_url(url)`
- Timepiece Perfection: `Scraper_Timepieceperfection.scrape_url(url)`

Treat these as reference or backup folders unless a user confirms they launch from them:

- `App-20260622T164520Z-3-001/App/Scraping App/App`
- `App-20260622T164520Z-3-001/App/App/FCT`
- `App-20260622T164520Z-3-001/App/App/reportes`
- `App-20260622T164520Z-3-001/App/Scraper Tool - MacOS_V2`

Do not edit vendored runtime folders:

- `env/`
- `myenv/`
- `__pycache__/`
- `site-packages/`

Do not read, rewrite, or include secrets from these files:

- `credentials.json`
- `ebay_token.json`
- `ebay_api_credentials.txt`

## Current Windows Findings

`Run_App.bat` creates or reuses a local `env`, installs dependencies, and starts `python MainApp.py`. This is the correct Windows entry point, but it should be verified from its own directory on a Windows machine because relative paths such as `settings.json`, `credentials.json`, and output `.txt` files depend on the current working directory.

The strongest existing candidate for a Windows scraper mismatch is Chrono24. The primary Windows folder uses a normal headless Selenium implementation in `App/App/scraper_chrono24.py`, while the duplicate `Scraping App/App/scraper_chrono24.py` contains a newer visible-browser `undetected_chromedriver` implementation. If the reported Windows problem is Chrono24 returning empty data or bot-blocked pages, the likely fix is to port the newer Chrono24 implementation into the primary Windows folder rather than create a new brand scraper.

The eBay product scraper currently uses the eBay Browse API in `scraper_ebay.py`, so many eBay failures are more likely to be credential/API/token/path issues than browser-driver issues. Credential contents must not be inspected while diagnosing.

## New Brand Scraper Decision

Create a new brand scraper only if the failing URL belongs to a domain that is not already recognized by `MainApp.py`.

A new brand scraper is convenient when all of these are true:

- The site is a public product page or collection page.
- Product details are available in static HTML or simple rendered HTML.
- The scraper can expose the existing adapter shape: `scrape_url(url)` returning a `pandas.DataFrame`.
- Output can fit the current columns: `Stock`, `URL`, `Make`, `Model`, `Reference Number`, `Year`, `Box`, `Papers`, `Original Price`.
- No login, CAPTCHA workflow, persistent Chrome profile, or broad app router rewrite is required.

Do not create a new brand scraper when the URL is already supported. In that case, repair the existing module or its Windows dependency/browser path.

## Recommended Next Step

Before implementation, collect one failing Windows example:

1. The exact URL that fails.
2. Which button/path was used: Scraper tab, Cliente Nuevo, or Cliente Recurrente.
3. The visible error or whether the result is simply empty.

Then choose one path:

- If the URL is Chrono24, repair `App/App/scraper_chrono24.py` by using the newer `undetected_chromedriver` approach already present in the duplicate Windows folder.
- If the URL is an already supported brand, repair only that scraper module and its minimal dispatch path.
- If the URL is an unsupported brand, add one new `Scraper_<Brand>.py` module and one minimal branch in `MainApp.py`.

## Verification Checklist

Run these from `App-20260622T164520Z-3-001/App/App` after changes:

```bat
Run_App.bat
```

For Python syntax verification, run:

```bat
python -m py_compile MainApp.py scraper_ebay.py scraper_chrono24.py scraper_swisstimepiececo.py Scraper_Wywatl.py Scraper_Thewatchoutlet.py Scraper_Grandcaliber.py Scraper_Boknowsluxury.py Scraper_Timepieceperfection.py Nuevos_Clientes.py google_loader.py ebay_auth.py scraper_vendedor.py
```

Do not stage or share generated outputs unless they are sanitized test fixtures.
