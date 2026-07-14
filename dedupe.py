"""Central memory of already-scraped items, shared by every scraper.

SQL based

The DB lives in db/. Update.py auto-update never touches it.

SQL concepts used here (one table, four statements):

  CREATE TABLE IF NOT EXISTS  creates the table only on first run.
  PRIMARY KEY (source, stock_id)  composite key: the *combination* must be unique, the key separates them per site. To ilustrate: Chrono123, eBay123.
  INSERT OR IGNORE  if the key already exists, skip the row instead of failing.
  SELECT stock_id, url FROM seen  reads everything seen to build the set.
"""
import requests
from datetime import datetime
from scraper_ebay import COLUMNS
import pandas as pd

# TEMP: until cloud
TURSO_URL = "libsql://grailzee-items-grail.aws-us-east-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODM2MjY2MTMsImlkIjoiMDE5ZjQ4NjYtNzIwMS03ZTEyLTlmNTctZGQwNzRiOGU4ZWI1Iiwia2lkIjoiVVVja2JONmUwNk5lVnh1TTh6VXJxMVlvSm9xNWZLTEJ1XzJZZG9OdDVoOCIsInJpZCI6IjYxMWE2MWUxLWExNzItNDE0OS05M2I5LTUzODdhNjZiNDQ0NyJ9.wcFtfM3QdsPtnwE6gx1EfZGI8aPoesgNeZNzz-DtIOa6GZylJ0cKRSXqHSePppMVMC8qrAtwfioUlqn1QhLBBA"

CREATE_TABLE_SQL = """CREATE TABLE IF NOT EXISTS seen (
    source              TEXT NOT NULL,
    stock_id            TEXT NOT NULL,
    url                 TEXT,
    make                TEXT,
    model               TEXT,
    reference_number    TEXT,
    year                TEXT,
    box                 TEXT,
    papers              TEXT,
    original_price      TEXT,
    customized          TEXT,
    category            TEXT,
    seller              TEXT,
    first_seen          TEXT,
    PRIMARY KEY (source, stock_id)
)"""

def _execute(statements):
    """statements: dict's list {"sql": ..., "args": [...]}. Send everything in a single HTTP pipeline."""
    http_url = TURSO_URL.replace("libsql://", "https://") + "/v2/pipeline"

    pipeline = [{"type": "execute", "stmt": s} for s in statements] + [{"type": "close"}]
    resp = requests.post(
        http_url,
        headers={"Authorization": f"Bearer {TURSO_TOKEN}"},
        json={"requests": pipeline},
    )
    resp.raise_for_status()
    return resp.json()["results"]

def _source_from_url(url):
    low = str(url).lower()
    if "ebay" in low:
        return "ebay"
    if "chrono24" in low:
        return "chrono24"
    return "other"


def known_ids():
    """Set of stock_ids and URLs already seen"""
    results = _execute([
        {"sql": CREATE_TABLE_SQL},
        {"sql": "SELECT stock_id, url FROM seen"},
    ])
    select_result = results[1]["response"]["result"]
    ids = set()
    for row in select_result["rows"]:
        stock_id = row[0]["value"]
        url = row[1]["value"] if row[1]["type"] != "null" else None
        ids.add(stock_id)
        if url:
            ids.add(url)
    return ids


def record_df(df):
    """Record the rows of a data-contract DataFrame. Returns how many were actually new."""
    if df is None or df.empty or "Stock" not in df.columns:
        return 0
    now = datetime.now().isoformat(timespec="seconds")

    insert_sql = """INSERT OR IGNORE INTO seen
        (source, stock_id, url, make, model, reference_number, year, box, papers, original_price, customized, category, seller, first_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    statements = [{"sql": CREATE_TABLE_SQL}]
    for _, r in df.iterrows():
        if str(r["Stock"]).strip() in ("", "nan", "Missing information"):
            continue
        args = [
            _source_from_url(r.get("URL", "")), str(r["Stock"]), str(r.get("URL", "")),
            str(r.get("Make", "")), str(r.get("Model", "")), str(r.get("Reference Number", "")),
            str(r.get("Year", "")), str(r.get("Box", "")), str(r.get("Papers", "")),
            str(r.get("Original Price", "")), str(r.get("Customized", "")), str(r.get("Category", "")), str(r.get("Seller", "")), now,
        ]
        statements.append({
            "sql": insert_sql,
            "args": [{"type": "text", "value": v} for v in args],
        })

    if len(statements) == 1:
        return 0

    results = _execute(statements)
    inserted = sum(
        1 for r in results[1:len(statements)] if r["response"]["result"]["affected_row_count"] == 1
    )
    return inserted

def fetch_rows(ids):
    if not ids:
        return pd.DataFrame(columns=COLUMNS)
    ids_to_sql = ", ".join(["?"] * len(ids))
    urls_to_sql = ", ".join(["?"] * len(ids))
    args = ids + ids
    results = _execute([{
        "sql": f"SELECT * FROM seen WHERE stock_id IN ({ids_to_sql}) OR url IN ({urls_to_sql})",
        "args": [{"type": "text", "value": v} for v in args], 
        }])
    items = []
    rows = results[0]["response"]["result"]
    for row in rows["rows"]:
        item = {
            "Stock": row[1]["value"],
            "URL": row[2]["value"],
            "Make": row[3]["value"],
            "Model": row[4]["value"],
            "Reference Number": row[5]["value"],
            "Year": row[6]["value"],
            "Box": row[7]["value"],
            "Papers": row[8]["value"],
            "Original Price": row[9]["value"],
            "Customized": row[10]["value"],
            "Category": row[11]["value"],
            "Seller": row[12]["value"],
        }
        items.append(item)
    return pd.DataFrame(items, columns=COLUMNS)