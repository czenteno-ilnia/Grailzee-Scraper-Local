# Grailzee Scraping Tool

[![Download](https://img.shields.io/badge/Download-Google%20Drive-4285F4?logo=googledrive&logoColor=white)](https://drive.google.com/drive/folders/1q2Wv2fsp4TV4n4DE6oBXyNzGS24Sn-r_?usp=sharing)
[![Questions](https://img.shields.io/badge/Questions-Slack-4A154B?logo=slack&logoColor=white)](https://slack.com/app_redirect?channel=C0BCW4D5XL6)
[![Contact](https://img.shields.io/badge/Contact-Email-EA4335?logo=maildotru&logoColor=white)](mailto:c.zenteno@unoro.com)

Extracts watch product data from sellers' catalogs (Chrono24, eBay, and seller websites) into a standardized CSV the White Glove team can review and submit, instead of copy-pasting each listing by hand.

## How to Run

Download the app folder: https://drive.google.com/drive/folders/1q2Wv2fsp4TV4n4DE6oBXyNzGS24Sn-r_?usp=sharing

The folder includes a step-by-step guide for each OS ([Guía_Windows](https://docs.google.com/document/d/1ztgk7OVoaJUUcYeVqY25Sf-I3eTYeUDwhRUIIj-eAxY/edit?usp=drive_link), [Guía_Mac](https://docs.google.com/document/d/1zrpoqeTPu4rvvfvGmGu1irjMtFEzaHIT9QRX7Lw6nuY/edit?usp=drive_link), [Guía_Chromebook](https://docs.google.com/document/d/12s8pDg0YmY3dx4I7Sa1Zq7s58j9JSQXqzjgkjhxu8HU/edit?usp=drive_link)) and a [Credenciales](https://docs.google.com/document/d/121sncyB2stWANpzYaf8GEkpHiSw0a5J_jS2rAZdX_Rs/edit?usp=drive_link) guide.
Quick reference:

- Windows: double-click `Windows.bat`
- macOS: double-click `Mac.command`
- Linux or Chromebook with Linux enabled: run `./app.sh`

The launchers create a local virtual environment, install `requirements.txt`, and start `MainApp.py`.

Notes:

- eBay requires Oxylabs credentials (see the `Credenciales` guide).
- Chrono24 does not use Oxylabs. It tries normal requests first, then falls back to Chrome/Selenium if needed.
- Google Chrome should be installed for the Chrono24 fallback.

## Problem

White Glove agents manually visit each seller's catalog, open every product, and copy-paste the data into the "Enterprise Clients" spreadsheet.
With ~74 customers a full update takes up to a week, it does not scale as sellers join, and manual copy-paste causes typos and missing fields.

## Goals

1. Cut manual catalog processing time by at least 50%.
2. Cover all current White Glove sellers (~74) and scale as new sellers join.
3. One standardized data structure across every source.
4. Detect new vs. existing products reliably by SKU and/or product link.
5. Add and remove sellers easily.

Required fields: Stock Number, Link, Make, Model, Reference Number, Box (Y/N), Papers (Y/N), Year, Price.

## Approach

The key decision: we scale by platform, not by seller.
The ~74 sellers run on only a handful of website platforms.
We do not write 74 scrapers; we write one scraper per platform, and every seller on that platform is covered for free.

Wherever a platform exposes an official JSON or API endpoint, we use it instead of scraping HTML.
JSON is faster, needs no proxy, and breaks far less often than HTML, so this also lowers ongoing maintenance.
The API and JSON platforms are the easy wins; Wix and custom sites are the hard, slow part.

| Category | Approach 
|---|---
| Shared base (data contract, CSV output, dedup) | Built once, every scraper reuses it
| Chrono24 | Done (requests, Selenium fallback) 
| eBay | Done (Oxylabs HTML); moving to official Browse API 
| Shopify | Most stores expose `/products.json`, one scraper covers all Shopify sellers, no proxy
| WooCommerce | Public Store API `/wp-json/wc/store/products`, HTML fallback 
| Squarespace | Many pages accept `?format=json` 
| Wix | Embedded JSON or Wix Stores API 
| Eleftra / custom sites | Bespoke per site, count is open-ended 

## Estimate & Roadmap

Realistic horizon for the full local tool including testing: ~2 to 2.5 months. A bare "it runs" version is reachable in ~1.5 months, but the extra weeks buy a tool that is cloud-ready and low-maintenance rather than brittle: JSON/API endpoints preferred over fragile HTML, a clean separation (scraping / output / launcher) so the cloud phase reuses this code instead of rewriting it, plus retries, logging, and tests. That up-front solidity saves future dev time. Custom sites are open-ended and depend on how many sellers use them. The cloud phase is separate and later (see below).

Planned weekly deliverables, one shippable KPI each, each removing more manual catalog work:

| Week | Deliverable | Sites covered | Team benefit (load lightened) |
|---|---|---|---|
| Now | Chrono24 + eBay scrapers (working) | Chrono24 (4): Exclusive Diamonds, Sivils Luxury, Diamond Crush Jewelry Inc, Alux Watches. eBay (16): WWC LLC, Watches of Charlotte, Timepiece of Mind, Watches on Demand, Fusion Jewelers NYC, Yourself Watches, Modern Swiss, Empire Time, Veryspecialbrand, TDTimepieces, Wristocrates/Wrist Flex Timepieces, Trading for Time, Clock Work, QD Watches, Luxe-Source, Elevated Luxe | Two sources already automated |
| 1 | Shared base: data contract + standardized CSV output | — | Every source lands in the exact format the spreadsheet expects, no reformatting |
| 2 | Deduplication + basic run logging | — | Weekly re-runs bring only new products; runs are traceable |
| 3 | Shopify scraper | Shopify (14): Timepiece Perfection, Ben Binyaminov, Only Chrono, Bayam, ElegantSwiss, DJP Jewelers, Bo Knows Luxury, East Coast Jewelry, Swiss Watch And Diamond Exchange, LXY Philly, NW Timepieces, The Watch Outlet, Nagi Jewelers, Time to Trust Watches | Biggest quick win: all Shopify sellers off manual copy-paste in one drop |
| 4 | Squarespace scraper | Squarespace (3): MVV Watches, Mechanical Art, Elevated Time Watch | Squarespace sellers onboarded; bulk of API-based sellers now automated |
| 5 | Wix + Elefta scrapers | Wix (1): The Watch Grande. Elefta (2): OT Watch Repair, SwissIce | Wix and Elefta sellers onboarded |
| 6 | WooCommerce scraper | WooCommerce (2): Pure Timepieces, Sansom Watches | WooCommerce sellers onboarded |
| 7 | Custom site scrapers + basic tests | Custom (2): SecondTime, Essential-Watches | Bespoke sellers automated; tests catch a broken scraper |
| 8 | eBay moved to official Browse API | Same 16 eBay sellers, more reliable | Structured data, no proxy, more reliable and evergreen |
| 9 and 10 | Hardening (retries/backoff, logging, full test coverage) | All sources | Edge cases handled, reliable weekly operation, cloud-ready |

## Where This Fits (Future)

This tool is the local, short-term step.
The longer goal is a cloud solution where data-entry agents trigger scrapes from a web UI instead of running scripts locally.
Once that is mature and running on a VPS or cloud (a separate, longer phase, roughly the month 4 to 6 range), the solution can be integrated with Grailzee's house developers, and its standardized output can feed other initiatives (batch listing / submission automation, automated reserves).

To keep that path open at no cost today, the architecture keeps three things separate:

- Scraping logic: pure, takes a URL, returns a list of product records.
- Output: CSV now; Google Sheets, BigQuery, or an API later.
- Launcher: local `.bat`/`.sh` now; a web UI later.

Candidates for the cloud phase (not built yet):

- Cloudflare Browser Rendering

## Technical

### Data Contract

Every scraper returns a product record with these fields.
Missing fields are returned as `None` or `"Missing"` and flagged, never silently dropped.

| Field | Type | Notes |
|---|---|---|
| `stock_number` | string | SKU or internal listing ID |
| `link` | string | Canonical product URL |
| `make` | string | Brand |
| `model` | string | Model |
| `reference_number` | string | Manufacturer reference |
| `box` | Yes/No/Missing | Box included |
| `papers` | Yes/No/Missing | Papers included |
| `year` | int or None | Production year |
| `price` | string/float or None | Listed price |
| `source` | string | Platform name |

### Scraping Flow

Same two-step flow for every source.

Profile (catalog) flow: receive seller profile or search URL and the set of already-scraped IDs, paginate listings up to a limit, skip already-scraped URLs or SKUs, extract each new listing, write output.

Item flow: receive one product URL, extract all fields, flag missing or mismatched fields, return the record.

### Error Handling

| Scenario | Behavior |
|---|---|
| Field missing on source | Return `Missing`, log, continue |
| Field mismatch (description vs. specs) | Flag for manual review, do not auto-resolve |
| Bot detection or blocked request | Retry with backoff, switch to proxy if available |
| Selector fails | Log, skip listing, continue run |
| Network timeout | Retry up to 3 times, then log and skip |

### Proxies

Chrono24 uses a Selenium browser fallback when plain requests are blocked.
eBay uses Oxylabs credentials today and will move to the official Browse API.
Other platforms are tried without proxies first (JSON endpoints rarely need them) and fall back to a proxy on block detection.

## Risks

- Platform changes (eBay, Chrono24, others) can break scrapers; ongoing maintenance required. Preferring JSON endpoints over HTML reduces this.
- Rate limits or anti-bot measures may cap scraping frequency.
- Custom seller sites vary widely and need per-site configuration.
- Mismatched fields (description vs. structured specs) may still need manual cross-validation.
