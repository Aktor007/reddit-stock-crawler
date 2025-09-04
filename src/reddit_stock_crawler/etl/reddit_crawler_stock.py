#!/usr/bin/env python3
# =============================================================================
# reddit_crawler_stock.py – WSB-Crawler  +  “Hot-Ticker-Report”
# Version 2025-08-20-b  (Erweitert um Top-/Growth-Abfragen)
# =============================================================================
"""
Neuerungen
==========
1.  Nach dem Crawl wird automatisch ein *Report* erzeugt:
      •  Top-15-Ticker nach Mentions (heute)
      •  Top-15-Ticker mit größtem Anstieg ggü. gestern
2.  Die SQL-Snippets aus der Anfrage sind 1-zu-1 integriert.
3.  Per CLI-Flag `--no-report` lässt sich der Report abschalten.

Benötigte Pakete (unverändert)
------------------------------
pip install praw python-dotenv tqdm pandas matplotlib tabulate
"""
# -----------------------------------------------------------------------------
# Standard-Bibliothek
# -----------------------------------------------------------------------------
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

# -----------------------------------------------------------------------------
# Third-Party
# -----------------------------------------------------------------------------
import praw                               # Reddit-API
import prawcore                           # HTTP-Fehler & 429
from dotenv import load_dotenv
from tqdm import tqdm
from tabulate import tabulate             # hübsche Tabellen-Ausgabe

# -----------------------------------------------------------------------------
# Konstanten / Defaults
# -----------------------------------------------------------------------------
BASE_DIR          = Path(__file__).resolve().parent
SCHEMA_FILE       = BASE_DIR / "schema.sql"
DEFAULT_DB        = "reddit_stock.db"
DEFAULT_SUBREDDIT = "wallstreetbets"
DEFAULT_POSTS     = 25
DEFAULT_COMMENTS  = 100
DEFAULT_ALERT_TH  = 10
DEFAULT_DELAY     = 1.0
TICKER_FILE       = "tickers_nasdaq.csv"

TOP_N             = 15    # Report-Größe
MIN_MENTIONS      = 5     # Schwellwert für Growth-Liste

MAX_AUTHORS_PER_MIN = 50  # Rate-limit-konformer Profil-Batch

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
def init_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt   = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(level=level, format=fmt)

# -----------------------------------------------------------------------------
# Reddit-Session
# -----------------------------------------------------------------------------
def get_reddit() -> praw.Reddit:
    load_dotenv()
    reddit = praw.Reddit(
        client_id       = os.getenv("REDDIT_CLIENT_ID"),
        client_secret   = os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent      = os.getenv(
            "REDDIT_USER_AGENT",
            "reddit_stock_crawler/1.0 (+github.com/you)",
        ),
        username        = os.getenv("REDDIT_USERNAME"),
        password        = os.getenv("REDDIT_PASSWORD"),
        check_for_async = False,
        ratelimit_seconds = 600,          # PRAW darf bis zu 10 min warten
    )
    _ = reddit.auth.limits               # Smoke-Test
    logging.debug("Reddit-Limits: %s", reddit.auth.limits)
    return reddit

# -----------------------------------------------------------------------------
# DB-Helper
# -----------------------------------------------------------------------------
def open_db(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    new  = (path == Path(":memory:")) or (not path.exists())

    conn = sqlite3.connect(
        path if path != Path(":memory:") else ":memory:",
        timeout=60,
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    conn.execute("PRAGMA foreign_keys = ON")

    if new and SCHEMA_FILE.exists():
        logging.info("Erstelle neues DB-Schema (%s)", SCHEMA_FILE.name)
        with SCHEMA_FILE.open() as fh:
            conn.executescript(fh.read())
    return conn


def ensure_sample_tickers(cur: sqlite3.Cursor) -> None:
    """zwei Demo-Ticker AAPL & TSLA – standardmäßig aktiv"""
    cur.executemany(
        """
        INSERT OR IGNORE INTO tickers(
          symbol, unternehmensname, sektor, branche, aktiv)
        VALUES(?,?,?,?,1)
        """,
        [
            ("AAPL", "Apple Inc.", "Technology", "Consumer Electronics"),
            ("TSLA", "Tesla Inc.", "Automotive", "Auto Manufacturers"),
        ],
    )


def fetch_known_tickers(cur: sqlite3.Cursor) -> Set[str]:
    return {row[0] for row in cur.execute(
        "SELECT symbol FROM tickers WHERE aktiv=1"
    )}

# -----------------------------------------------------------------------------
# Ticker-Logik
# -----------------------------------------------------------------------------
TICKER_RE = re.compile(r"\b\$?([A-Z]{1,5})\b")

# --> neue Stop-Word-Liste gegen False-Positiv
AMBIGUOUS = {
    "YOU", "ON", "T", "BE", "SO", "UP","AS", "OR", "CAN", "HAS", "NOW", "HE", "BY", "AN", "AND", "AM", "ANY", "BEAT", "AGO",
    "IS", "WHERE", "NOT", "BRO", "SAY", "POST", "PLAY", "DAY", "SEE", "NEXT", "WELL", "WWW", "WAY", "HOPE", "BULL", "CARE", "CASH",
    "COOK", "COST", "LUCK", "OP", "MAN", "MOVE", "TOP", "JOB", "ELSE", "EVER", "FLOW", "LOW", "LOT", "REAL", "PUMP", "ROOT", "HIT", 
    "NICE", "RUN", "NEAR", "BIT", "TWO", "ONE", "ADD", "BASE", "HUT", "PAY", "TRUE", "WTF", "GAIN", "AREN", "DEEP", "CUZ", "EAT", "FACT",
    "LINE", "APP", "WOW", "AIN", "EDIT", "EXP", "FAT", "PLUS", "BILL", "DRUG", "MAX", "NET", "AI", "K", "F", "VS", "LINK", "FORM"

}

def load_ticker_white_list(path: str | Path) -> Set[str]:
    """liest CSV/TSV – erste Spalte == Symbol"""
    path = Path(path)
    if not path.exists():
        logging.warning("Ticker-Datei %s nicht gefunden, nutze nur DB-Ticker", path)
        return set()

    symbols: set[str] = set()
    with path.open(newline="") as fh:
        dialect = csv.Sniffer().sniff(fh.read(1024))
        fh.seek(0)
        reader  = csv.DictReader(fh, dialect=dialect)
        col     = reader.fieldnames[0]
        for row in reader:
            sym = row[col].strip().upper()
            if 0 < len(sym) <= 5 and sym.isalpha():
                symbols.add(sym)

    logging.info("Ticker-White-List geladen: %d Symbole", len(symbols))
    return symbols


def extract_mentions(text: str, allowed: Set[str]) -> List[str]:
    """liefert alle erlaubten Ticker im Text"""
    text_u = text.upper()
    
    return [m for m in TICKER_RE.findall(text_u) if m in allowed and m not in AMBIGUOUS]

# -----------------------------------------------------------------------------
# Insert-Funktionen
# -----------------------------------------------------------------------------
def upsert_subreddit(cur, sr) -> None:
    cur.execute(
        """
        INSERT INTO subreddits(
          id,title,description,subscriber,created_utc,quarantaene)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
          title         = excluded.title,
          description   = excluded.description,
          subscriber    = excluded.subscriber,
          quarantaene   = excluded.quarantaene
        """,
        (
            sr.display_name,
            sr.title,
            sr.public_description,
            sr.subscribers,
            int(sr.created_utc),
            int(getattr(sr, "quarantine", False)),
        ),
    )


# ------------------------------------------------------------------ #
# NEU: Username nur vormerken – später anreichern ------------------- #
# ------------------------------------------------------------------ #
def queue_redditor(cur: sqlite3.Cursor, name: Optional[str]) -> None:
    """
    Legt nur den Usernamen an. Alle Stats bleiben zunächst NULL.
    Tabelle 'redditors' **muss** NULL-Werte erlauben.
    """
    if not name:          # None oder "[deleted]"
        return
    cur.execute(
        "INSERT OR IGNORE INTO redditors(id) VALUES(?)",
        (name,),
    )
# ------------------------------------------------------------------ #


def insert_post(cur, p) -> None:
    cur.execute(
        """
        INSERT OR IGNORE INTO posts(
          id,subreddit_id,author_id,title,selftext,is_self,url,permalink,
          score,upvote_ratio,num_comments,created_utc,is_original_content,
          is_video,over_18,spoiler,stickied,locked,saved,clicked)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            p.id,
            p.subreddit.display_name,
            p.author.name if p.author else None,
            p.title,
            p.selftext,
            int(p.is_self),
            p.url,
            p.permalink,
            p.score,
            p.upvote_ratio,
            p.num_comments,
            int(p.created_utc),
            int(getattr(p, "is_original_content", False)),
            int(p.is_video),
            int(p.over_18),
            int(getattr(p, "spoiler", False)),
            int(p.stickied),
            int(p.locked),
            int(getattr(p, "saved", False)),
            int(getattr(p, "clicked", False)),
        ),
    )


def insert_comment(cur, c, post_id: str) -> None:
    parent_id = (
        c.parent_id.split("_")[1]
        if c.parent_id and c.parent_id.startswith("t3_")
        else None
    )
    cur.execute(
        """
        INSERT OR IGNORE INTO comments(
          id,post_id,parent_id,author_id,body,score,created_utc,
          distinguished,is_submitter,stickied,locked,depth)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            c.id,
            post_id,
            parent_id,
            c.author.name if c.author else None,
            c.body,
            c.score,
            int(c.created_utc),
            c.distinguished,
            int(getattr(c, "is_submitter", False)),
            int(c.stickied),
            int(c.locked),
            c.depth,
        ),
    )


def insert_mention(
    cur,
    sym: str,
    post_id: Optional[str],
    comment_id: Optional[str],
    source: str,
    context: str,
    pos: int,
) -> None:
    cur.execute(
        """
        INSERT INTO mentions(
          symbol,post_id,comment_id,source,context,position)
        VALUES(?,?,?,?,?,?)
        """,
        (sym, post_id, comment_id, source, context, pos),
    )

# -----------------------------------------------------------------------------
# Aggregation & Alerts
# -----------------------------------------------------------------------------
def update_daily_stats(conn) -> None:
    today = datetime.utcnow().date().isoformat()
    conn.executescript(
        f"""
        INSERT INTO daily_stats(
          symbol,date,mention_count,post_mentions,
          comment_mentions,unique_authors)
        SELECT  m.symbol,
                '{today}',
                COUNT(*),
                SUM(m.post_id    IS NOT NULL),
                SUM(m.comment_id IS NOT NULL),
                COUNT(DISTINCT COALESCE(p.author_id, c.author_id))
        FROM    mentions AS m
        LEFT JOIN posts    AS p ON p.id = m.post_id
        LEFT JOIN comments AS c ON c.id = m.comment_id
        WHERE   DATE(m.created_at) = DATE('now')
        GROUP BY m.symbol
        ON CONFLICT(symbol,date) DO UPDATE SET
          mention_count    = excluded.mention_count,
          post_mentions    = excluded.post_mentions,
          comment_mentions = excluded.comment_mentions,
          unique_authors   = excluded.unique_authors;
        """
    )


def update_trend_alerts(conn, threshold: int) -> None:
    cur = conn.execute(
        "SELECT symbol, mention_count FROM daily_stats "
        "WHERE date=DATE('now') AND mention_count>=?",
        (threshold,),
    )
    for symbol, cnt in cur:
        conn.execute(
            """
            INSERT OR IGNORE INTO trend_alerts(
              symbol,alert_type,threshold,current_value,percent_change,
              window_minutes,message,priority)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                symbol,
                "mention_spike",
                threshold,
                cnt,
                None,
                1440,
                f"{symbol} wurde heute bereits {cnt}× erwähnt.",
                "medium",
            ),
        )
    conn.commit()

# -----------------------------------------------------------------------------
# Report-SQL
# -----------------------------------------------------------------------------
SQL_TOP_MENTIONS = f"""
SELECT symbol,
       mention_count,
       post_mentions,
       comment_mentions,
       unique_authors
FROM   daily_stats
WHERE  date = DATE('now')
ORDER  BY mention_count DESC
LIMIT  {TOP_N};
"""

SQL_GROWTH = f"""
WITH today AS (
  SELECT symbol, mention_count
  FROM   daily_stats
  WHERE  date = DATE('now')
),
yesterday AS (
  SELECT symbol, mention_count AS mc_y
  FROM   daily_stats
  WHERE  date = DATE('now','-1 day')
)
SELECT t.symbol,
       t.mention_count       AS mc_today,
       y.mc_y,
       ROUND(1.0 * t.mention_count / NULLIF(y.mc_y,0),2) AS growth_factor
FROM   today t
LEFT   JOIN yesterday y USING(symbol)
WHERE  t.mention_count >= {MIN_MENTIONS}
  AND (y.mc_y IS NULL OR t.mention_count > 2*y.mc_y)
ORDER  BY growth_factor DESC
LIMIT  {TOP_N};
"""

# -----------------------------------------------------------------------------
# Export (unverändert)
# -----------------------------------------------------------------------------
def export_mentions(conn, out_dir: Path, today_only: bool = True) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    sql = "SELECT * FROM mentions"
    if today_only:
        sql += " WHERE DATE(created_at)=DATE('now')"
    rows = conn.execute(sql).fetchall()
    cols = [d[0] for d in conn.execute(sql).description]

    # JSON-Lines
    with (out_dir / "mentions.json").open("w") as fh:
        for row in rows:
            fh.write(json.dumps(dict(zip(cols, row))) + "\n")

    # CSV
    with (out_dir / "mentions.csv").open("w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(cols)
        wr.writerows(rows)

    logging.info("Export geschrieben (%d Zeilen)", len(rows))

# -----------------------------------------------------------------------------
# Rate-limited Author-Enrichment
# -----------------------------------------------------------------------------
def enrich_authors(
    conn: sqlite3.Connection,
    reddit: praw.Reddit,
    batch: int = MAX_AUTHORS_PER_MIN,
) -> None:
    """
    Holt für 'batch' Autoren fehlende Karma-Daten und schreibt sie zurück.
    """
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT id FROM redditors
        WHERE link_karma IS NULL
        ORDER BY id
        LIMIT ?
        """,
        (batch,),
    ).fetchall()

    if not rows:
        logging.info("Enrichment: nichts zu tun.")
        return

    logging.info("Enrichment: %d Autoren werden angereichert (≤%d/min)",
                 len(rows), MAX_AUTHORS_PER_MIN)

    start = time.monotonic()
    processed = 0
    for name, in rows:
        try:
            r = reddit.redditor(name)
            r._fetch()  # 1 GET
            cur.execute(
                """
                UPDATE redditors
                   SET link_karma    = ?,
                       comment_karma = ?,
                       created_utc   = ?
                 WHERE id = ?
                """,
                (r.link_karma, r.comment_karma, int(r.created_utc), name),
            )
            conn.commit()
            processed += 1
            time.sleep(60 / MAX_AUTHORS_PER_MIN)  # gleichmäßig verteilen

        except prawcore.exceptions.NotFound:
            # User existiert nicht / gelöscht
            cur.execute(
                "UPDATE redditors SET link_karma=0 WHERE id=?", (name,)
            )
            conn.commit()

        except prawcore.exceptions.TooManyRequests as exc:
            retry = int(exc.response.headers.get("Retry-After", 60))
            logging.warning("Rate-Limit erreicht – Pause %ds", retry)
            time.sleep(retry + 1)
            break

        except Exception:
            logging.exception("Fehler beim Enrichment von %s", name)

    dur = time.monotonic() - start
    logging.info("Enrichment fertig (%d User | %.1fs)", processed, dur)

# -----------------------------------------------------------------------------
# Crawler-Klasse
# -----------------------------------------------------------------------------
class RedditStockCrawler:
    def __init__(
        self,
        db_file: str,
        subreddit: str,
        post_limit: int,
        comment_limit: int,
        alert_th: int,
        delay: float,
        ticker_file: Path,
        report: bool = True,
        enrich_only: bool = False,
    ):
        self.db_file       = db_file
        self.subreddit     = subreddit
        self.post_limit    = post_limit
        self.comment_limit = comment_limit
        self.alert_th      = alert_th
        self.delay         = delay
        self.ticker_file   = ticker_file
        self.reddit        = get_reddit()
        self.metrics       = defaultdict(int)
        self.make_report   = report
        self.enrich_only   = enrich_only

    # ------------------------------------------------------------------ #
    def _print_query(
        self,
        conn: sqlite3.Connection,
        sql: str,
        title: str,
        headers: Sequence[str] | None = None,
    ) -> None:
        rows = conn.execute(sql).fetchall()
        if not rows:
            logging.info("Report '%s': keine Daten.", title)
            return

        print("\n" + "=" * 78)
        print(f"{title}")
        print("=" * 78)
        print(
            tabulate(
                rows,
                headers=headers or [d[0] for d in conn.execute(sql).description],
                tablefmt="github",
            )
        )

    def _run_report(self, conn: sqlite3.Connection) -> None:
        """führt die beiden SQL-Snippets aus und druckt sie"""
        self._print_query(conn, SQL_TOP_MENTIONS,
                          f"🔥 Top {TOP_N} Mentions heute")
        self._print_query(conn, SQL_GROWTH,
                          f"🚀 Größter Anstieg ggü. gestern "
                          f"(min {MIN_MENTIONS} Mentions)")

    # ------------------------------------------------------------------ #
    def crawl(self) -> None:
        if self.enrich_only:
            # Nur Worker-Modus (Cron)
            with open_db(self.db_file) as conn:
                enrich_authors(conn, self.reddit)
            return

        t0 = time.time()
        logging.info("Crawler-Run gestartet (r/%s)", self.subreddit)

        with open_db(self.db_file) as conn:
            cur = conn.cursor()
            ensure_sample_tickers(cur)

            whitelist = (
                fetch_known_tickers(cur)
                | load_ticker_white_list(self.ticker_file)
            )
            if not whitelist:
                logging.warning("Whitelist leer – es werden keine Mentions erkannt!")

            # Stammdaten Subreddit
            sr = self.reddit.subreddit(self.subreddit)
            upsert_subreddit(cur, sr)
            conn.commit()

            # -------- Posts --------------------------------------------------
            for post in tqdm(
                sr.new(limit=self.post_limit),
                total=self.post_limit,
                desc="Posts",
                unit="post",
            ):
                queue_redditor(cur, post.author.name if post.author else None)
                insert_post(cur, post)
                self.metrics["posts"] += 1

                # Mentions im Post
                for m in extract_mentions(
                    f"{post.title} {post.selftext}", whitelist
                ):
                    insert_mention(
                        cur, m, post.id, None, "post", post.title[:250], 0
                    )
                    self.metrics["mentions"] += 1

                # Kommentare
                post.comments.replace_more(limit=0)
                comments = post.comments.list()
                comments.sort(key=lambda c: c.depth)

                for cm in comments[: self.comment_limit]:
                    queue_redditor(cur, cm.author.name if cm.author else None)
                    insert_comment(cur, cm, post.id)
                    self.metrics["comments"] += 1

                    for m in extract_mentions(cm.body, whitelist):
                        insert_mention(
                            cur, m, None, cm.id, "comment", cm.body[:250], 0
                        )
                        self.metrics["mentions"] += 1

                conn.commit()
                time.sleep(self.delay)  # Respect Rate-Limit

            # -------- Nachbereitung -----------------------------------------
            update_daily_stats(conn)
            update_trend_alerts(conn, self.alert_th)
            export_mentions(conn, BASE_DIR / "exports", today_only=True)

            if self.make_report:
                self._run_report(conn)

            # -------- Profil-Daten nachtragen -------------------------------
            enrich_authors(conn, self.reddit)

            dt = time.time() - t0
            logging.info(
                f"Fertig: {self.metrics['posts']} Posts | "
                f"{self.metrics['comments']} Kommentare | "
                f"{self.metrics['mentions']} Mentions | {dt:.1f} s"
            )

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="reddit_crawler_stock",
        description="Reddit-Crawler für Aktien-Mentions (+ Trend-Report)",
    )
    p.add_argument("--db", default=DEFAULT_DB, help="SQLite-Datei")
    p.add_argument("-s", "--subreddit", default=DEFAULT_SUBREDDIT)
    p.add_argument("-p", "--posts", type=int, default=DEFAULT_POSTS)
    p.add_argument("-c", "--comments", type=int, default=DEFAULT_COMMENTS)
    p.add_argument("-t", "--threshold", type=int, default=DEFAULT_ALERT_TH)
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    p.add_argument("--ticker-file", default=TICKER_FILE)
    p.add_argument("--no-report", action="store_true",
                   help="keine Hot-Ticker-Ausgabe nach dem Crawl")
    p.add_argument("--enrich-only", action="store_true",
                   help="nur fehlende Karma-Daten anreichern")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    init_logging(args.verbose)

    try:
        crawler = RedditStockCrawler(
            db_file=args.db,
            subreddit=args.subreddit,
            post_limit=args.posts,
            comment_limit=args.comments,
            alert_th=args.threshold,
            delay=args.delay,
            ticker_file=Path(args.ticker_file),
            report=not args.no_report,
            enrich_only=args.enrich_only,
        )
        crawler.crawl()

    except KeyboardInterrupt:
        logging.warning("Abbruch durch Benutzer")
    except Exception:
        logging.exception("Unerwarteter Fehler")
        sys.exit(1)


if __name__ == "__main__":
    main()
