"""Central memory of already-scraped items, shared by every scraper.

SQL based

The DB lives in db/. Update.py auto-update never touches it.

SQL concepts used here (one table, four statements):

  CREATE TABLE IF NOT EXISTS  creates the table only on first run.
  PRIMARY KEY (source, stock_id)  composite key: the *combination* must be unique, the key separates them per site. To ilustrate: Chrono123, eBay123.
  INSERT OR IGNORE  if the key already exists, skip the row instead of failing.
  SELECT stock_id, url FROM seen  reads everything seen to build the set.
"""
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join("db", "seen_ids.sqlite3")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS seen (
               source     TEXT NOT NULL,   -- "ebay", "chrono24", ...
               stock_id   TEXT NOT NULL,   -- site's canonical ID (item id, listing code)
               url        TEXT,            -- canonical item URL
               first_seen TEXT,            -- ISO timestamp of first sighting
               PRIMARY KEY (source, stock_id)
           )"""
    )
    return conn


def _source_from_url(url):
    low = str(url).lower()
    if "ebay" in low:
        return "ebay"
    if "chrono24" in low:
        return "chrono24"
    return "other"


def known_ids():
    """Set of stock_ids and URLs already seen, scrapers retrieve from here."""
    with _connect() as conn:
        rows = conn.execute("SELECT stock_id, url FROM seen").fetchall()
    ids = set()
    for stock_id, url in rows:
        ids.add(stock_id)
        if url:
            ids.add(url)
    return ids


def record_df(df):
    """Record the rows of a data-contract DataFrame (Stock, URL). Returns how many were actually new (INSERT OR IGNORE skips repeats)."""
    if df is None or df.empty or "Stock" not in df.columns:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    rows = [
        (_source_from_url(r.get("URL", "")), str(r["Stock"]), str(r.get("URL", "")), now)
        for _, r in df.iterrows()
        if str(r["Stock"]).strip() not in ("", "nan", "Missing information")
    ]
    with _connect() as conn:
        cur = conn.executemany(
            "INSERT OR IGNORE INTO seen (source, stock_id, url, first_seen) VALUES (?, ?, ?, ?)",
            rows,
        )
        return cur.rowcount