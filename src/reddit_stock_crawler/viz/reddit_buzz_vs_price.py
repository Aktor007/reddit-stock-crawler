#!/usr/bin/env python3
# ============================================================================
# reddit_buzz_vs_price_overlay.py
#
#   – Buzz-Balken sind immer ≤ Preis-Balken
#   – auf dem Buzz-Balken steht der prozentuale Buzz-Wert
#   – Tage/Ticker ohne *beide* Werte werden ausgeblendet
#
#   3-D-PLOT (ENDGÜLTIGE ACHSENBELEGUNG)
#   ------------------------------------
#   X-Achse (links ↔ rechts)   : Ticker
#   Y-Achse (Tiefe)            : Datum
#   Z-Achse (nach oben)        : Schlusskurs in USD (Balkenhöhe)
#   Farbe                      : Buzz-Level (Mentions / Tag)
# ============================================================================
from __future__ import annotations

# ----------------------------------------------------------- Std-Libs
import argparse
import hashlib
import logging
import pickle
import sqlite3
import warnings
from pathlib import Path

# ----------------------------------------------------------- 3rd-Party
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf
from matplotlib.widgets import Slider
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401  (benötigt für 3-D)

# ----------------------------------------------------------- Logging / Cache
CACHE_DIR = Path.home() / ".cache" / "reddit_buzz"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("buzz_vs_price")


def init_logging(verbose: bool = False) -> None:
    lvl = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(level=lvl, format=fmt, force=True)
    if not verbose:
        logging.getLogger("yfinance").setLevel(logging.WARNING)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)


# ----------------------------------------------------------- Mini-Disk-Cache
def _cache_key(prefix: str, *parts: str) -> Path:
    h = hashlib.sha1("::".join(parts).encode()).hexdigest()
    return CACHE_DIR / f"{prefix}_{h}.pkl"


def cached(func):
    """winziger Pickle-Disk-Cache"""
    def wrapper(*args, **kwargs):
        key = _cache_key(func.__name__, repr(args), repr(kwargs))
        if key.exists():
            try:
                return pickle.loads(key.read_bytes())
            except Exception:
                key.unlink(missing_ok=True)
        res = func(*args, **kwargs)
        try:
            key.write_bytes(pickle.dumps(res, protocol=4))
        except Exception:
            pass
        return res
    return wrapper


# ----------------------------------------------------------- Buzz laden
@cached
def load_buzz(
    db: Path,
    start: str,
    end: str,
    symbols: list[str] | None,
    top_n: int,
) -> pd.DataFrame:
    """DataFrame (Index = date, Columns = Ticker) mit Mention-Counts"""
    with sqlite3.connect(db) as con:
        # ------------------------------- falls Ticker nicht per CLI vorgegeben
        if symbols is None:
            sql_top = """
                SELECT symbol, COUNT(*) AS mc
                FROM mentions
                WHERE date(created_at) BETWEEN ? AND ?
                GROUP BY symbol
                ORDER BY mc DESC
                LIMIT ?
            """
            symbols = [r[0] for r in con.execute(sql_top, (start, end, top_n))]
        if not symbols:
            raise RuntimeError("Keine Ticker gefunden – DB leer?")

        ph = ",".join("?" * len(symbols))

        # ------------------------------- daily_stats (falls vorhanden)
        sql_ds = f"""
            SELECT date, symbol, mention_count
            FROM daily_stats
            WHERE date BETWEEN ? AND ? AND symbol IN ({ph})
        """
        df_ds = pd.read_sql(sql_ds, con,
                            params=[start, end, *symbols],
                            parse_dates=["date"])

        # ------------------------------- Fallback: on-the-fly-Aggregation
        sql_mn = f"""
            SELECT date(created_at) AS date, symbol, COUNT(*) AS mention_count
            FROM mentions
            WHERE date(created_at) BETWEEN ? AND ? AND symbol IN ({ph})
            GROUP BY date, symbol
        """
        df_mn = pd.read_sql(sql_mn, con,
                            params=[start, end, *symbols],
                            parse_dates=["date"])

    df = (pd.concat([df_ds, df_mn], ignore_index=True)
            .drop_duplicates(subset=["date", "symbol"], keep="first"))

    buzz = (df.pivot(index="date", columns="symbol", values="mention_count")
              .fillna(0)
              .astype("uint32"))

    full = pd.date_range(start, end, freq="D")
    buzz = buzz.reindex(full, fill_value=0).astype("uint32")
    buzz.index.name = "date"
    return buzz


# ----------------------------------------------------------- Preise laden
@cached
def load_prices(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    end_plus = (pd.to_datetime(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    log.info("Lade Kurse für %s", ", ".join(symbols))
    close = yf.download(
        symbols,
        start=start,
        end=end_plus,
        progress=False,
        auto_adjust=True,
    )["Close"]

    if isinstance(close, pd.Series):          # nur 1 Symbol
        close = close.to_frame(name=symbols[0])
    elif isinstance(close.columns, pd.MultiIndex):
        close = close.droplevel(0, axis=1)

    close.index.name = "date"
    return close.astype("float32")


# ----------------------------------------------------------- 3-D-Plot  (Ticker=X | Datum=Y | Kurs=Z)
def plot_3d_overlay(
    buzz: pd.DataFrame,
    prices: pd.DataFrame,
    outfile: Path,
) -> None:
    """
    X-Achse : Ticker
    Y-Achse : Datum
    Z-Achse : Schlusskurs (USD)  – Balkenhöhe
    Farbe   : Buzz-Wert
    """
    common_idx = buzz.index.intersection(prices.index)
    if common_idx.empty:
        warnings.warn("Keine gemeinsamen Handelstage – 3-D-Plot übersprungen.")
        return
    buzz, prices = buzz.loc[common_idx], prices.loc[common_idx]

    norm = plt.Normalize(buzz.values.min(), buzz.values.max())
    cmap = plt.cm.Oranges

    tickers = list(buzz.columns)
    dates   = list(common_idx)

    xs, ys, zs, dx, dy, dz, colors = [], [], [], [], [], [], []
    for yi, day in enumerate(dates):
        for xi, sym in enumerate(tickers):
            m_cnt = buzz.at[day, sym]
            price = prices.at[day, sym]
            if pd.isna(price) or pd.isna(m_cnt):
                continue

            # --- Koordinaten
            xs.append(xi)          # X: Ticker-Index
            ys.append(yi)          # Y: Datum-Index (Reihe)
            zs.append(0)           # Z-Startpunkt = 0

            # --- Abmessungen
            dx.append(0.8)         # Breite (X-Richtung)
            dy.append(0.8)         # Tiefe  (Y-Richtung, kleine Lücke)
            dz.append(price)       # Höhe   (Z-Richtung)  = Schlusskurs

            colors.append(cmap(norm(m_cnt)))

    fig = plt.figure(figsize=(12, 7))
    ax  = fig.add_subplot(projection="3d")
    ax.bar3d(xs, ys, zs, dx, dy, dz,
             shade=True, color=colors,
             edgecolor="k", linewidth=0.3)

    # ----------- Achsenbeschriftungen & Ticks
    ax.set_xlabel("Ticker")
    ax.set_xticks(range(len(tickers)))
    ax.set_xticklabels(tickers, rotation=45, ha="right")

    ax.set_ylabel("Datum")
    step = max(1, len(dates) // 8)
    ax.set_yticks(range(0, len(dates), step))
    ax.set_yticklabels([d.strftime("%Y-%m-%d") for d in dates[::step]])

    ax.set_zlabel("Schlusskurs (USD)")

    # angenehmer Blickwinkel
    ax.view_init(elev=25, azim=-60)

    # Farblegende
    mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array([])
    cbar = fig.colorbar(mappable, ax=ax, pad=0.1)
    cbar.set_label("Mentions / Tag")

    ax.set_title("Reddit-Buzz (Farbe) vs. Schlusskurs (Höhe)")
    plt.tight_layout()
    fig.savefig(outfile, dpi=150)
    log.info("3-D-Plot gespeichert → %s", outfile)
    plt.close(fig)


# ----------------------------------------------------------- 2-D-Overlay + Slider
def plot_overlay_slider(
    buzz: pd.DataFrame,
    prices: pd.DataFrame,
    outfile: Path,
) -> None:
    """
    – blauer Rahmen  = Schlusskurs
    – orange Füllung = Mentions (0–100 % des blauen Balkens)
    – Prozentwert steht im Balken
    """
    common_idx = buzz.index.intersection(prices.index)
    if common_idx.empty:
        warnings.warn("Keine gemeinsamen Handelstage – Overlay übersprungen.")
        return

    tickers = list(buzz.columns)
    x = np.arange(len(tickers))

    width_outer = 0.80
    width_inner = 0.55

    fig, ax = plt.subplots(figsize=(11, 5))
    plt.subplots_adjust(bottom=0.23)        # Platz für Slider

    idx_initial = len(common_idx) - 1       # letzter Handelstag
    day_sel = common_idx[idx_initial]

    # ------------------------------------------------------- Hilfs-Fkt.
    def mask(day: pd.Timestamp) -> pd.Series:
        """True, wenn Preis vorhanden *und* Buzz > 0"""
        return (~prices.loc[day].isna()) & (buzz.loc[day] > 0)

    def buzz_height(day: pd.Timestamp) -> pd.Series:
        b = buzz.loc[day]
        p = prices.loc[day]
        b_max = b.max()
        return p * (b / b_max) if b_max > 0 else b * 0

    def buzz_pct(day: pd.Timestamp) -> pd.Series:
        b = buzz.loc[day]
        b_max = b.max()
        return (b / b_max * 100).round(1) if b_max > 0 else b * 0

    # ------------------------------------------------------- Initialer Plot
    m0         = mask(day_sel)
    price_vals = prices.loc[day_sel].where(m0, 0)
    buzz_vals  = buzz_height(day_sel).where(m0, 0)
    pct_vals   = buzz_pct(day_sel).where(m0, 0)

    bars_price = ax.bar(
        x, price_vals,
        width=width_outer,
        facecolor="none",
        edgecolor="tab:blue",
        linewidth=2.0,
        label="Schlusskurs (USD)",
        zorder=3,
    )

    bars_buzz = ax.bar(
        x, buzz_vals,
        width=width_inner,
        color="tab:orange",
        alpha=0.9,
        label="Mentions (rel.)",
        zorder=2,
    )

    # ---------------------------- Prozent-Labels im Balken
    labels: list[plt.Text] = []
    for xi, ok, h, pct in zip(x, m0, buzz_vals, pct_vals):
        if ok and h > 0:
            labels.append(
                ax.text(
                    xi, h * 0.5, f"{pct:.0f} %",
                    ha="center", va="center",
                    color="white", fontsize=8,
                    weight="bold", rotation=90,
                    zorder=4,
                )
            )
        else:
            labels.append(ax.text(0, 0, "", alpha=0))   # Dummy

    # ------------------------------------------------------- Optik
    ax.set_xticks(x)
    ax.set_xticklabels(tickers, rotation=45, ha="right")
    ax.set_ylabel("Schlusskurs (USD)", color="tab:blue")
    ax.set_title(f"Reddit-Buzz vs. Kurs – {day_sel.date()}")
    ax.legend(loc="upper left")

    # ------------------------------------------------------- Slider
    ax_slider = plt.axes([0.10, 0.08, 0.80, 0.05])
    slider = Slider(
        ax=ax_slider,
        label="Handelstag",
        valmin=0,
        valmax=len(common_idx) - 1,
        valinit=idx_initial,
        valstep=1,
    )

    def update(val):
        day = common_idx[int(val)]
        m   = mask(day)
        price_new = prices.loc[day].where(m, 0)
        buzz_new  = buzz_height(day).where(m, 0)
        pct_new   = buzz_pct(day).where(m, 0)

        for bar, h, ok in zip(bars_price, price_new, m):
            bar.set_height(h)
            bar.set_visible(bool(ok))
        for bar, h, ok in zip(bars_buzz, buzz_new, m):
            bar.set_height(h)
            bar.set_visible(bool(ok))

        for lbl in labels:
            lbl.remove()
        labels.clear()
        for xi, ok, h, pct in zip(x, m, buzz_new, pct_new):
            if ok and h > 0:
                labels.append(
                    ax.text(
                        xi, h * 0.5, f"{pct:.0f} %",
                        ha="center", va="center",
                        color="white", fontsize=8,
                        weight="bold", rotation=90,
                        zorder=4,
                    )
                )

        ax.set_title(f"Reddit-Buzz vs. Kurs – {day.date()}")
        ax.relim(); ax.autoscale_view()
        fig.canvas.draw_idle()

    slider.on_changed(update)

    # ------------------------------------------------------- Screenshot + GUI
    fig.savefig(outfile, dpi=150)
    log.info("Overlay-PNG gespeichert → %s (interaktives Fenster folgt)", outfile)
    plt.show()
    plt.close(fig)


# ----------------------------------------------------------- Hilfsfunktionen
def last_trading_day(ref: pd.Timestamp) -> pd.Timestamp:
    nyse = mcal.get_calendar("NYSE")
    sched = nyse.schedule(start_date=ref - pd.Timedelta(days=7), end_date=ref)
    return sched.index[-1].tz_localize(None).normalize()


# ----------------------------------------------------------- CLI
def cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="reddit_buzz_vs_price_overlay",
        description="Reddit-Buzz vs. Schlusskurs (3-D + interaktiver Overlay-Slider)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--db", default="reddit_stock.db")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("-t", "--tickers", nargs="+")
    p.add_argument("--top", type=int, default=5,
                   help="Top-N Ticker (falls --tickers leer)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


# ----------------------------------------------------------- Main
def main() -> None:
    args = cli()
    init_logging(args.verbose)

    start = pd.to_datetime(args.start).normalize()
    end   = pd.to_datetime(args.end).normalize()

    ltd = last_trading_day(pd.Timestamp.utcnow().normalize())
    if end > ltd:
        log.info("End-Datum %s > letzter Handelstag %s – setze %s",
                 end.date(), ltd.date(), ltd.date())
        end = ltd

    start_s, end_s = start.date().isoformat(), end.date().isoformat()
    log.info("Range: %s → %s | top=%d", start_s, end_s, args.top)

    buzz = load_buzz(Path(args.db), start_s, end_s, args.tickers, args.top)
    if buzz.empty:
        log.error("Kein Buzz gefunden – Abbruch.")
        return

    prices = load_prices(buzz.columns.tolist(), start_s, end_s)
    prices = prices.dropna(axis=1, how="all")
    if prices.empty:
        log.error("Keine Kursdaten gefunden – Abbruch.")
        return

    plot_3d_overlay(
        buzz=buzz,
        prices=prices,
        outfile=Path("buzz_vs_price_3d.png"),
    )

    plot_overlay_slider(
        buzz=buzz,
        prices=prices,
        outfile=Path("buzz_vs_price_overlay.png"),
    )


if __name__ == "__main__":
    main()