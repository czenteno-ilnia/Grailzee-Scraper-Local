"""Central memory of already-scraped items, shared by every scraper.

SQL based

The DB lives in db/. Update.py auto-update never touches it.

SQL concepts used here (one table, four statements):

  CREATE TABLE IF NOT EXISTS  creates the table only on first run.
  PRIMARY KEY (source, stock_id)  composite key: the *combination* must be unique, the key separates them per site. To ilustrate: Chrono123, eBay123.
  INSERT OR IGNORE  if the key already exists, skip the row instead of failing.
   SELECT stock_id, url FROM the selected table reads everything seen to build the set.
"""
import os

import requests
from scraper_ebay import COLUMNS
import pandas as pd
from shopify_url import direct_product_key, verified_direct_product_key

# TEMP: until cloud
TURSO_URL = "libsql://grailzee-items-grail.aws-us-east-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODM2MjY2MTMsImlkIjoiMDE5ZjQ4NjYtNzIwMS03ZTEyLTlmNTctZGQwNzRiOGU4ZWI1Iiwia2lkIjoiVVVja2JONmUwNk5lVnh1TTh6VXJxMVlvSm9xNWZLTEJ1XzJZZG9OdDVoOCIsInJpZCI6IjYxMWE2MWUxLWExNzItNDE0OS05M2I5LTUzODdhNjZiNDQ0NyJ9.wcFtfM3QdsPtnwE6gx1EfZGI8aPoesgNeZNzz-DtIOa6GZylJ0cKRSXqHSePppMVMC8qrAtwfioUlqn1QhLBBA"
SHOPIFY_SOURCE = "Shopify"
DEDUPE_TABLE_ENV = "GRAILZEE_DEDUPE_TABLE"
PRODUCTION_DEDUPE_TABLE = "seen"
SHOPIFY_TEST_DEDUPE_TABLE = "seen_shopify_test"
ALLOWED_DEDUPE_TABLES = frozenset({PRODUCTION_DEDUPE_TABLE, SHOPIFY_TEST_DEDUPE_TABLE})

CREATE_TABLE_SQL = """CREATE TABLE IF NOT EXISTS {table_name} (
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


class InvalidDedupeTableName(ValueError):
    pass


def _dedupe_table():
    table_name = os.environ.get(DEDUPE_TABLE_ENV, PRODUCTION_DEDUPE_TABLE)
    if table_name not in ALLOWED_DEDUPE_TABLES:
        raise InvalidDedupeTableName(
            f"{DEDUPE_TABLE_ENV} must be {PRODUCTION_DEDUPE_TABLE!r} or {SHOPIFY_TEST_DEDUPE_TABLE!r}"
        )
    return table_name

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

def _source_from_url(url, stock_id=""):
    if str(stock_id).lower().startswith("shopify:"):
        return SHOPIFY_SOURCE
    low = str(url).lower()
    if ".myshopify.com" in low:
        return SHOPIFY_SOURCE
    if "ebay" in low:
        return "ebay"
    if "chrono24" in low:
        return "chrono24"
    return "other"


def identity_from_values(stock_id, url):
    return (_source_from_url(url, stock_id), str(stock_id))


def ids_for_source(known_ids, source):
    return {value for known_source, value in known_ids if known_source == source}


def known_ids():
    table_name = _dedupe_table()
    results = _execute([
        {"sql": CREATE_TABLE_SQL.format(table_name=table_name)},
        {"sql": f"SELECT source, stock_id, url FROM {table_name}"},
    ])
    select_result = results[1]["response"]["result"]
    ids = set()
    for row in select_result["rows"]:
        stock_id = row[1]["value"]
        url = row[2]["value"] if row[2]["type"] != "null" else ""
        source = _source_from_url(url, stock_id)
        if source == "other":
            source = row[0]["value"]
        ids.add((source, stock_id))
        if url:
            ids.add((source, url))
            shopify_product_key = direct_product_key(url)
            if source == SHOPIFY_SOURCE and not shopify_product_key:
                shopify_product_key = verified_direct_product_key(url)
            if source == SHOPIFY_SOURCE and shopify_product_key:
                ids.add((source, shopify_product_key))
    return ids


def record_df(df):
    """Record the rows of a data-contract DataFrame. Returns how many were actually new."""
    if df is None or df.empty or "Stock" not in df.columns:
        return 0
    table_name = _dedupe_table()
    insert_sql = f"""INSERT OR IGNORE INTO {table_name}
        (source, stock_id, url, make, model, reference_number, year, box, papers, original_price, customized, category, seller, first_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"""

    statements: list[dict[str, str | list[dict[str, str]]]] = [
        {"sql": CREATE_TABLE_SQL.format(table_name=table_name)}
    ]
    for _, r in df.iterrows():
        if str(r["Stock"]).strip() in ("", "nan", "Missing information"):
            continue
        args = [
            _source_from_url(r.get("URL", ""), r["Stock"]), str(r["Stock"]), str(r.get("URL", "")),
            str(r.get("Make", "")), str(r.get("Model", "")), str(r.get("Reference Number", "")),
            str(r.get("Year", "")), str(r.get("Box", "")), str(r.get("Papers", "")),
            str(r.get("Original Price", "")), str(r.get("Customized", "")), str(r.get("Category", "")), str(r.get("Seller", "")),
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

def distinct_sellers():
    """Available sellers, for the historical-pull dropdown."""
    table_name = _dedupe_table()
    results = _execute([
        {"sql": f"SELECT DISTINCT seller FROM {table_name} WHERE seller IS NOT NULL AND seller != '' ORDER BY seller"},
    ])
    rows = results[0]["response"]["result"]["rows"]
    return [row[0]["value"] for row in rows]


def _fetch_seen(where_sql="", args=None):
    # Explicit columns, in COLUMNS + [Source, first_seen] order; independent of schema order.
    table_name = _dedupe_table()
    results = _execute([{
        "sql": f"""SELECT stock_id, url, make, model, reference_number, year, box, papers,
            original_price, customized, category, seller, source, first_seen
            FROM {table_name}{where_sql}
            ORDER BY CASE WHEN first_seen IS NULL OR first_seen = '' THEN 1 ELSE 0 END,
                     first_seen DESC""",
        "args": [{"type": "text", "value": v} for v in (args or [])],
    }])
    rows = results[0]["response"]["result"]["rows"]
    items = [
        [cell["value"] if cell["type"] != "null" else "" for cell in row]
        for row in rows
    ]
    return pd.DataFrame(items, columns=pd.Index(COLUMNS + ["Source", "first_seen"]))


def fetch_by_seller(seller):
    """Everything already scraped for a seller. Mixes sources on purpose: the Source column disambiguates."""
    return _fetch_seen(" WHERE seller = ?", [seller])


def fetch_all():
    """The whole seen table, for a full historical export."""
    return _fetch_seen()


def fetch_rows(ids):
    if not ids:
        return pd.DataFrame(columns=pd.Index(COLUMNS))
    table_name = _dedupe_table()
    ids_to_sql = ", ".join(["?"] * len(ids))
    urls_to_sql = ", ".join(["?"] * len(ids))
    args = ids + ids
    results = _execute([{
        "sql": f"SELECT * FROM {table_name} WHERE stock_id IN ({ids_to_sql}) OR url IN ({urls_to_sql})",
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
    return pd.DataFrame(items, columns=pd.Index(COLUMNS))
