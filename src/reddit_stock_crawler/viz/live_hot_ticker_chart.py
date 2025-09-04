#!/usr/bin/env python3
"""
live_hot_ticker_chart.py
------------------------
Zeigt eine dynamische Balkengrafik der aktuell meist-diskutierten Ticker
(basierend auf Tabelle `daily_stats`, date = DATE('now')).
"""

from __future__ import annotations
import sqlite3, sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as anim

# --------------------------------------------------------------------------- #
# Parameter – ggf. anpassen
# --------------------------------------------------------------------------- #
DB_FILE      = Path("reddit_stock.db")   # Pfad zu deiner SQLite-DB
TOP_N        = 15                        # wie viele Ticker anzeigen?
REFRESH_SEC  = 60                        # Sekunden bis zur nächsten Aktualisierung
COLOR_MAP    = plt.cm.tab20              # Farbschema (20 diskrete Farben)

# --------------------------------------------------------------------------- #
def fetch_today_stats(n: int = TOP_N) -> pd.DataFrame:
    """Liest TOP-N-Ticker (heutige Mentions) aus der Datenbank"""
    with sqlite3.connect(DB_FILE) as conn:
        sql = f"""
        SELECT symbol,
               mention_count AS mentions,
               post_mentions,
               comment_mentions,
               unique_authors
        FROM   daily_stats
        WHERE  date = DATE('now')
        ORDER  BY mentions DESC
        LIMIT  {n};
        """
        return pd.read_sql(sql, conn)


# --------------------------------------------------------------------------- #
# Matplotlib-Animation
# --------------------------------------------------------------------------- #
def update(frame_idx: int) -> None:
    """Wird alle `REFRESH_SEC` Sekunden aufgerufen und zeichnet das Diagramm neu"""
    ax.clear()
    df = fetch_today_stats()
    if df.empty:
        ax.text(0.5, 0.5, "Noch keine Daten für heute 🤷‍♂️",
                ha="center", va="center", fontsize=14)
        return

    bars = ax.bar(df.index, df["mentions"],
                  color=[COLOR_MAP(i % COLOR_MAP.N) for i in range(len(df))])

    # Balken beschriften
    for bar, val, sym in zip(bars, df["mentions"], df["symbol"]):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{sym}\n{val}",
                ha="center", va="bottom", fontsize=9)

    # Achsen / Titel
    ax.set_xticks([])
    ax.set_ylabel("Mentions heute")
    ax.set_title(f"🔥 Top {TOP_N} am {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC")
    ax.margins(y=0.15)


if __name__ == "__main__":
    if not DB_FILE.exists():
        sys.exit(f"DB-Datei '{DB_FILE}' nicht gefunden!")

    fig, ax = plt.subplots(figsize=(10, 6))
    ani = anim.FuncAnimation(fig, update, interval=REFRESH_SEC * 1000)
    plt.tight_layout()
    plt.show()