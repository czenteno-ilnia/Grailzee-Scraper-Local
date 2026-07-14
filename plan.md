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

Secondary:
5. [ ] (Phase 2) Create a Google Cloud project.
6. [ ] (Phase 2) Service account + share sheet as Viewer + daily pull script (`gspread` or `google-api-python-client`).
7. [ ] (Phase 2) Cross-check logic sheet vs. Turso → gap report.

## Next steps: "Sin datos" + logging (added 2026-07-13)

Goal: no silent failed items in production, and enough signal to find the root cause of "Sin datos" on healthy links (5 Oxylabs retries already in place, still happens sometimes).

Target: "Sin datos" = 0 cases. Every link pasted yields a CSV row — links are manually curated before pasting, so a genuinely dead listing is the only acceptable miss, and that case must be detected and logged as such (not a generic "Sin datos").

8. [x] Complete CSV via Turso: item already in db → fetch full row from `seen` instead of skipping (`fetch_rows()` in dedupe.py + MainApp wiring). CSV always delivers every pasted link, zero extra Oxylabs requests, survives mid-batch credit cutoffs/restarts. Done 2026-07-14, commit `32afdef`.
9. [ ] Diagnose "Sin datos" root cause: map every path that ends in an empty result (Oxylabs fail / empty content / parse finds no specs+price). Dump failing HTML + page <title> to logs — title distinguishes dead listing vs block page vs layout change.
10. [ ] Workaround per case: dead listing → distinct log + marker in CSV; anything else → retry/fix until it scrapes. "Sin datos" on a healthy link = bug, not an outcome.
11. [ ] New `events` table in Turso (ts, machine, level, stage, stock_id/url, reason, detail) + wiring refactor: every log point in the program (fetch retries, parse failures, dedupe skips, batch summary) also writes a structured row there. Logging via stdlib `logging` + handlers (terminal/UI/Turso).

- [ ] Map seller field from Chrono24
- [ ] Seller pagination early-cutoff: force newest-first sort (eBay `_sop=10`, Chrono24 `sortorder=5&pageSize=120`). New seller → extract everything; known seller → stop after N consecutive already-seen items (N = 1 full page).
  - Note: CSV + Turso only persist at batch end a mid-batch cut loses all  scrapes. Fix later: incremental persist (per item or chunk) + scrape links oldest-first (`item_links.reverse()`), so any cut leaves the gap at the newest end, which the next newest-first pagination rediscovers naturally. Do before or with the cutoff.

## Demo day priority (demo 2026-07-15)
Paste seller URL → zero "Sin datos". Focus: steps 9-10 above.

---
Notes:
Do we need to include (sub)categories for Chrono24? Everything is watches
If a pasted item is already in Turso, do we show it in the csv or not?