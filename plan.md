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
1. [ ] Turso account, create database, save `url`+`token` in `local/turso_credentials.json` (gitignored).
2. [ ] `pip install libsql-experimental`.
3. [ ] Rewrite `dedupe.py`: connect to Turso instead of local sqlite3 (same schema `seen(source, stock_id, url, first_seen)`).
4. [ ] Decide whether local stays as an offline cache or gets removed (decide once remote works).
5. [ ] (Phase 2) Create a Google Cloud project.
6. [ ] (Phase 2) Service account + share sheet as Viewer + daily pull script (`gspread` or `google-api-python-client`).
7. [ ] (Phase 2) Cross-check logic sheet vs. Turso → gap report.