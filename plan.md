# Plan: centralize backend (week of 2026-07-09)

## Objective
Move scraped-item tracking from per-machine (`db/seen_ids.sqlite3` local) to a central backend.

## Decisions made
- **Backend: Turso** (remote SQLite, free tier). Same schema already in `dedupe.py`.
- **Data contract:** full `COLUMNS` (Stock, URL, Make, Model, Reference Number, Year, Box, Papers, Original Price, Customized) + `first_seen` (scrape date). Still uses `INSERT OR IGNORE`.
- **Two mechanisms:**
  1. Program records (Turso): what actually got scraped.
  2. Team spreadsheet (Google Sheets): what has already been scraped and submitted by the team to the 'Externals' sheets. Cross-checking both surfaces gaps.
  Note: Migration of all records to the new Externals sheets approach is still in progress. Estimated completion: next week.

## Steps
1. [x] Turso account, create database, save `url`+`token` in `local/turso_credentials.json` (gitignored).
2. [x] ~~`pip install libsql-experimental`~~ dropped, segfaults on connect with `sync_url`+`auth_token`. Using Turso's HTTP `/v2/pipeline` API via `requests` instead. Verified test working.
3. [x] Rewrite `dedupe.py`: connect to Turso via HTTP API instead of local sqlite3 (same schema `seen`, now with full item columns).
4. [x] Local `db/` removed (2026-07-10). No offline cache. Turso is single source of truth.
5. [ ] (Phase 2) Create a Google Cloud project.
6. [ ] (Phase 2) Service account + share sheet as Viewer + daily pull script (`gspread` or `google-api-python-client`).
7. [ ] (Phase 2) Cross-check logic sheet vs. Turso → gap report.
