# Plan: centralize backend (week of 2026-07-09)

## 2026-07-16

- [x] Import eBay history: 6,004 covered; 5,586 inserted; rollback logged.
- [x] Import Chrono24 history: 2,943 covered; 2,859 inserted; rollback logged.
- [x] Backfill Chrono sellers: 107 updated; 0 blank; rollback logged.
- [x] Validate visible `WG` rows, IDs, duplicates, conflicts and seller names.
- [x] Keep marketplace seller identities separate (`source` scopes them).
- [x] Skip known single-item links from requests/CSV (`2d37920`).
- [x] Generate new scraper timestamps in Turso UTC; focused test passed.

Pending commits:

- `fix(dedupe): use Turso UTC timestamps` — `dedupe.py`, `tests/unit/test_dedupe.py`
- `docs: record completed data migrations` — `plan.md`

Keep spreadsheets, migration scripts, reports and rollback logs under ignored `local/`.

## Objective
Move scraped-item tracking from per-machine (`db/seen_ids.sqlite3` local) to a central backend.

## Decisions made
- **Backend: Turso** (remote SQLite, free tier). Same schema already in `dedupe.py`.
- **Data contract:** full `COLUMNS` (Stock, URL, Make, Model, Reference Number, Year, Box, Papers, Original Price, Customized) + `first_seen` (scrape date). Still uses `INSERT OR IGNORE`.
- **Two mechanisms:**
  1. Program records (Turso): what actually got scraped.
  2. Team spreadsheet (Google Sheets): what has already been scraped and submitted by the team to the 'Externals' sheets. Cross-checking both surfaces gaps.
  Note: Historical eBay and Chrono24 migration completed 2026-07-16.

## Steps
1. [x] Turso account, create database, save `url`+`token` in `local/turso_credentials.json` (gitignored).
2. [x] ~~`pip install libsql-experimental`~~ dropped, segfaults on connect with `sync_url`+`auth_token`. Using Turso's HTTP `/v2/pipeline` API via `requests` instead. Verified test working.
3. [x] Rewrite `dedupe.py`: connect to Turso via HTTP API instead of local sqlite3 (same schema `seen`, now with full item columns).
4. [x] Local `db/` removed (2026-07-10). No offline cache. Turso is single source of truth.

Secondary:
5. [ ] (Phase 2) Create a Google Cloud project.
6. [ ] (Phase 2) Service account + share sheet as Viewer + daily pull script (`gspread` or `google-api-python-client`).
7. [ ] (Phase 2) Cross-check logic sheet vs. Turso → gap report.

## Next steps: "Sin datos" + logging (added 2026-07-13)

Goal: no silent failed items in production, and enough signal to find the root cause of "Sin datos" on healthy links (5 Oxylabs retries already in place, still happens sometimes).

Target: "Sin datos" = 0 cases. Every link pasted yields a CSV row — links are manually curated before pasting, so a genuinely dead listing is the only acceptable miss, and that case must be detected and logged as such (not a generic "Sin datos").

8. [x] Dedupe para links individuales (decisión actualizada 2026-07-15): si el item ya existe en Turso o en el CSV del batch, no se devuelve ninguna fila al CSV y no se hace ningún request. El log informa `Este item ya está scrapeado`. Las URLs de seller mantienen su comportamiento: sólo devuelven items nuevos.
9. [x] Failures append a marker row to the CSV ("No se pudo extraer. Comprobar manualmente"). Excluded from Turso and dedupe, so re-pasting retries them. 
- [x] Seller pagination early-cutoff, eBay: forces `_sop=10` (newest first) + stops after `SEEN_STREAK_CUTOFF = 20` consecutive already-seen items. New seller never triggers it (nothing seen). Verified live: known seller = 1 pagination request instead of full crawl. Raise threshold toward 240 (full page) after sheet backfill.


Pending:
- [ ] Same cutoff for Chrono24 (`sortorder=5&pageSize=120` + streak in `collect_listing_urls`). 
- [x] Backfill Turso from team sheets (eBay and Chrono24 completed 2026-07-16 with rollback logs).
10. [ ] Diagnose "Sin datos" root cause: map every path that ends in an empty result (Oxylabs fail / empty content / parse finds no specs+price). Dump failing HTML + page <title> to logs — title distinguishes dead listing vs block page vs layout 
11. [ ] New `events` table in Turso (ts, machine, level, stage, stock_id/url, reason, detail) + wiring refactor: every log point in the program (fetch retries, parse failures, dedupe skips, batch summary) also writes a structured row there. Logging via stdlib `logging` + handlers (terminal/UI/Turso).
- [x] Map and backfill seller field from Chrono24 (107 corrected; 0 empty).


Maybe:
- [ ] Add `first_seen` column to CSV output (already in Turso schema). Tells the team new vs old per row.
  - Note: CSV + Turso only persist at batch end; a mid-batch cut loses all scrapes. Fix later: incremental persist (per item or chunk) + scrape links oldest-first (`item_links.reverse()`), so any cut leaves the gap at the newest end, which the next newest-first pagination rediscovers naturally.
- [ ] CSV naming: `{seller}_{date}.csv` instead of plain batch date

---
Notes:
- Do we need to include (sub)categories for Chrono24? Everything is watches
- [x] Si un item individual pegado ya está en Turso, no se muestra en el CSV; sólo se informa en logs (decidido 2026-07-15).


For seller workflow:
- Return all items, signaling/column(already-scraped)/seen_timestap only new ones
- Return only new items

Just for items:
- [x] Return only new items; known items are reported only in logs.

What if a user wants to retrieve already scraped data?
