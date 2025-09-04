# tests/test_crawler_stub.py
from types import SimpleNamespace as NS
from reddit_crawler_stock import RedditStockCrawler
import tempfile, pathlib

class FakeComment(NS): pass
class FakePost(NS): pass
class FakeSubreddit(NS): pass

def test_crawler_with_stub():
    tmpdb = tempfile.mktemp(suffix=".db")
    crawler = RedditStockCrawler(
        db_file       = tmpdb,
        subreddit_name= "fake",
        post_limit    = 1,
        comment_limit = 1,
        alert_threshold=1,
        rate_delay    = 0,
        ticker_file   = "tickers_nasdaq.csv"   # oder leer
    )

    # Reddit-Session ersetzen
    post = FakePost(
        id="p1", subreddit=NS(display_name="fake"),
        author=None, title="$AAPL to the moon", selftext="",
        is_self=True, url="", permalink="",
        score=1, upvote_ratio=1, num_comments=0, created_utc=0,
        is_original_content=False, is_video=False, over_18=False,
        spoiler=False, stickied=False, locked=False, saved=False, clicked=False,
        comments=NS(list=lambda: [], replace_more=lambda limit=0: None)
    )
    crawler.reddit = NS(subreddit=lambda name: NS(
        display_name="fake", title="", public_description="",
        subscribers=0, created_utc=0, quarantine=False,
        new=lambda limit: [post]
    ))

    crawler.crawl()
    # Nun liegt in tmpdb mindestens 1 Mention
    import sqlite3, os
    conn = sqlite3.connect(tmpdb)
    cnt, = conn.execute("SELECT COUNT(*) FROM mentions").fetchone()
    assert cnt == 1
    os.remove(tmpdb)