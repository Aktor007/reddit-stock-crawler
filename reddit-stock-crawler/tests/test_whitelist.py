# tests/test_whitelist.py
import sqlite3, tempfile, os
from reddit_crawler_stock import open_db, ensure_sample_tickers, fetch_known_tickers

def test_sample_tickers_are_active():
    # temporäre In-Memory-DB
    conn = open_db(":memory:")
    cur  = conn.cursor()
    # Tabelle minimal nachbilden
    cur.execute("""CREATE TABLE tickers(
                    symbol TEXT PRIMARY KEY,
                    unternehmensname TEXT,
                    sektor TEXT,
                    branche TEXT,
                    aktiv INTEGER DEFAULT 1)""")
    ensure_sample_tickers(cur)
    conn.commit()

    wl = fetch_known_tickers(cur)
    assert {"AAPL", "TSLA"} <= wl, "Whitelist ist leer → Mentions können nie erkannt werden"