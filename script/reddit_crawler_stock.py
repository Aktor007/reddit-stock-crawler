#!/usr/bin/env python3
# =============================================================================
# reddit_crawler_stock.py  –  WSB-Crawler + “Hot-Ticker-Report” (Rich-Edition)
# Version 2025-09-06-rich-1
# =============================================================================
"""
➊  Unveränderter Crawl- und DB-Code (gekürzt kommentiert)
➋  NEU: hübsche Balkengrafik im Terminal mit *Rich* anstelle der
    ASCII-Tabellen.  
    •  pip install rich  
    •  keine weitere Abhängigkeit / kein GUI nötig
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
from typing import List, Optional, Sequence, Set

# -----------------------------------------------------------------------------
# Third-Party
# -----------------------------------------------------------------------------
import praw
import prawcore
from dotenv import load_dotenv
from tqdm import tqdm
from tabulate import tabulate          # wird noch für Fallback gebraucht
from rich.console import Console       #  <-- NEU
from rich.progress import Progress, BarColumn, TextColumn  #  <-- NEU

# -----------------------------------------------------------------------------
# Konstanten
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

TOP_N             = 15
MIN_MENTIONS      = 5
MAX_AUTHORS_PER_MIN = 50

console = Console()     #  <-- globale Rich-Konsole
# -----------------------------------------------------------------------------
# (der komplette, unveränderte Hauptcode folgt – ausgeklappt gekürzt)
# -----------------------------------------------------------------------------
# …  alle Funktionen aus deiner Originaldatei bleiben 1-zu-1 erhalten  …
#     (open_db, ensure_sample_tickers, fetch_known_tickers, extract_mentions,
#      insert_post, insert_comment, insert_mention, update_*  usw.)
# -----------------------------------------------------------------------------
# SQL-Snippets bleiben unverändert
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
# Helfer für Rich-Balkengrafik
# -----------------------------------------------------------------------------
def _rich_bar_chart(
    rows: list[tuple],
    label_col: int,
    value_col: int,
    title: str,
    max_width: int = 40,
    color: str = "cyan",
) -> None:
    """Zeigt horizontale Balken für (label,value)-Tupel mit Rich."""
    if not rows:
        console.print(f"[yellow]{title}: keine Daten.[/]")
        return

    console.rule(f"[bold]{title}")
    total_max = max(r[value_col] for r in rows)

    with Progress(
        TextColumn("[bold blue]{task.fields[label]}"),
        BarColumn(bar_width=max_width, complete_style=color),
        TextColumn("[bold]{task.completed}"),
        console=console,
    ) as progress:
        for lab, val, *rest in rows:     # weitere Spalten werden ignoriert
            progress.add_task("", total=total_max, completed=val, label=lab)

# -----------------------------------------------------------------------------
# Crawler-Klasse (unverändert bis auf _run_report)
# -----------------------------------------------------------------------------
class RedditStockCrawler:
    # __init__ (identisch)  …

    # ------------------------------------------------------- #
    def _run_report(self, conn: sqlite3.Connection) -> None:
        """Ersetzt die Tabulate-Tabellen durch Rich-BarCharts."""
        cur = conn.cursor()

        # ----- Top-Mentions ---------------------------------
        rows_top = cur.execute(SQL_TOP_MENTIONS).fetchall()
        _rich_bar_chart(
            rows_top,
            label_col=0,
            value_col=1,
            title=f"🔥 Top {TOP_N} Mentions heute",
            color="bright_green",
        )

        # ----- Growth-Faktor -------------------------------
        rows_grow = cur.execute(SQL_GROWTH).fetchall()
        _rich_bar_chart(
            rows_grow,
            label_col=0,
            value_col=3,         # growth_factor
            title=f"🚀 Größter Anstieg ggü. gestern (min {MIN_MENTIONS} Mentions)",
            color="magenta",
        )

    # crawl()  bleibt unverändert
    # ------------------------------------------------------- #

# -----------------------------------------------------------------------------
# CLI + main() bleiben unverändert
# -----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="reddit_crawler_stock",
        description="Reddit-Crawler für Aktien-Mentions (+ Rich-Dashboard)",
    )
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("-s", "--subreddit", default=DEFAULT_SUBREDDIT)
    p.add_argument("-p", "--posts", type=int, default=DEFAULT_POSTS)
    p.add_argument("-c", "--comments", type=int, default=DEFAULT_COMMENTS)
    p.add_argument("-t", "--threshold", type=int, default=DEFAULT_ALERT_TH)
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    p.add_argument("--ticker-file", default=TICKER_FILE)
    p.add_argument("--no-report", action="store_true")
    p.add_argument("--enrich-only", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def init_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s | %(levelname)-8s | %(message)s"
    logging.basicConfig(level=level, format=fmt)


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
        console.print("[yellow]Abbruch durch Benutzer.[/]")
    except Exception:
        logging.exception("Unerwarteter Fehler")
        sys.exit(1)


if __name__ == "__main__":
    main()
