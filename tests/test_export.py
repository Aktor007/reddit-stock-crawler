# tests/test_export.py
import sqlite3, tempfile, pathlib, json, csv
from reddit_crawler_stock import export_mentions

def test_export_writes_files():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE mentions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT, post_id TEXT, comment_id TEXT, source TEXT,
        context TEXT, position INT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("INSERT INTO mentions(symbol,post_id,source,context,position) VALUES('TSLA','p1','post','TSLA',0)")
    outdir = pathlib.Path(tempfile.mkdtemp())
    export_mentions(conn, outdir, today_only=False)
    assert (outdir/"mentions.json").exists()
    assert (outdir/"mentions.csv").exists()