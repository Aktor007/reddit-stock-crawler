# tests/test_db_mentions.py
import sqlite3
from reddit_crawler_stock import insert_mention

def test_insert_mention():
    conn = sqlite3.connect(":memory:")
    cur  = conn.cursor()
    cur.execute("""CREATE TABLE mentions(
                    symbol TEXT,
                    post_id TEXT,
                    comment_id TEXT,
                    source TEXT,
                    context TEXT,
                    position INTEGER
                 )""")
    insert_mention(cur, "AAPL", "abc", None, "post", "Buy AAPL", 0)
    conn.commit()
    cnt, = cur.execute("SELECT COUNT(*) FROM mentions").fetchone()
    assert cnt == 1