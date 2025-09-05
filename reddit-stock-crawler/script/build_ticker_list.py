#!/usr/bin/env python3
# ============================================================================ #
# build_ticker_list.py – Multi-Exchange White-List-Generator
# ============================================================================ #

# Erzeugt eine CSV-Whitelist (»tickers_nasdaq.csv«) für den Reddit-Crawler.


from __future__ import annotations

import argparse
import csv
import logging
import sys
import io
import time
from pathlib import Path
from typing import Final, Iterable

import concurrent.futures as cf
import pandas as pd
import requests
from wordfreq import zipf_frequency

try:
    import yfinance as yf           # nur bei --verify genutzt
except ImportError:
    yf = None                       # noqa: N816

# --------------------------------------------------------------------------- #
# Konstanten
# --------------------------------------------------------------------------- #
OUT_FILE: Final[Path] = Path("tickers_nasdaq.csv")

HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
REQUEST_KWARGS: Final[dict] = dict(headers=HEADERS, timeout=30)

KEEP_SINGLE: Final[set[str]] = {"F", "T", "O", "K"}
MANUAL_STOP: Final[set[str]] = {
    "ALL", "ARE", "BUY", "CALL", "CEO", "CFO", "MOON", "OPEN", "PLAN", "SELL",
    "USA", "NEW", "GOOD", "LOVE", "YOLO", "DD", "BIG", "DAY", "OUT",
}

# --------------------------------------------------------------------------- #
# Hilfs-Decorator
# --------------------------------------------------------------------------- #
def retry(max_tries: int = 3, pause: float = 3.0):


    def deco(fn):
        def wrapper(*args, **kwargs):
            for att in range(1, max_tries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    if att == max_tries:
                        raise
                    logging.warning("%s() fehlgeschlagen (%s) – Retry %d/%d",
                                    fn.__name__, exc, att, max_tries)
                    time.sleep(pause * att)

        return wrapper

    return deco


# --------------------------------------------------------------------------- #
# HTTP-/HTML-Hilfsfunktionen
# --------------------------------------------------------------------------- #
@retry()
def _get_html(url: str) -> str:

    return requests.get(url, **REQUEST_KWARGS).text


def _tables_from_url(url: str, **read_html_kwargs) -> list[pd.DataFrame]:

    html = _get_html(url)
    return pd.read_html(io.StringIO(html), **read_html_kwargs)


# --------------------------------------------------------------------------- #
# Quellen – USA
# --------------------------------------------------------------------------- #
@retry()
def fetch_nasdaq() -> set[str]:
    url = "https://api.nasdaq.com/api/screener/stocks?download=true"
    rows = requests.get(url, **REQUEST_KWARGS).json()["data"]["rows"]
    return {r["symbol"].upper() for r in rows}


def fetch_sp500() -> set[str]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tbl = _tables_from_url(url, header=0)[0]
    return set(tbl["Symbol"].str.upper())


# --------------------------------------------------------------------------- #
# Quellen – Deutschland
# --------------------------------------------------------------------------- #
DE_INDEX_PAGES: Final[dict[str, str]] = {
    "DAX": "https://en.wikipedia.org/wiki/DAX",
    "MDAX": "https://en.wikipedia.org/wiki/MDAX",
    "SDAX": "https://en.wikipedia.org/wiki/SDAX",
    "TecDAX": "https://en.wikipedia.org/wiki/TecDAX",
}


def _extract_wiki_tickers(url: str,
                          column_hint: str = "Ticker") -> set[str]:
    out: set[str] = set()
    for df in _tables_from_url(url):
        for col in df.columns:
            if column_hint.lower() in str(col).lower():
                out |= set(df[col].astype(str).str.upper())
    return out


def fetch_germany() -> set[str]:
    out: set[str] = set()
    for name, url in DE_INDEX_PAGES.items():
        logging.info("Lade %s …", name)
        out |= _extract_wiki_tickers(url)
    return {s.replace(".DE", "") for s in out}   # Suffix entfernen


# --------------------------------------------------------------------------- #
# Quellen – China ADR
# --------------------------------------------------------------------------- #
ADR_PAGES: Final[list[str]] = [
    "https://en.wikipedia.org/wiki/"
    "List_of_Chinese_companies_listed_on_the_Nasdaq",
    "https://en.wikipedia.org/wiki/"
    "List_of_Chinese_companies_listed_on_the_New_York_Stock_Exchange",
]


def fetch_china_adr() -> set[str]:
    out: set[str] = set()
    for url in ADR_PAGES:
        logging.info("Lade China-ADR-Liste …")
        out |= _extract_wiki_tickers(url, "Ticker")
    return out


# --------------------------------------------------------------------------- #
# Crypto
# --------------------------------------------------------------------------- #
@retry()
def fetch_crypto(top: int = 250) -> set[str]:
    url = ("https://api.coingecko.com/api/v3/coins/markets"
           "?vs_currency=usd&order=market_cap_desc&sparkline=false"
           f"&per_page={top}&page=1")
    data = requests.get(url, **REQUEST_KWARGS).json()
    return {c["symbol"].upper() for c in data
            if c["symbol"].isalpha() and 2 <= len(c["symbol"]) <= 5}


# --------------------------------------------------------------------------- #
# Cleaning / Validation
# --------------------------------------------------------------------------- #
def _looks_like_word(sym: str) -> bool:

    return zipf_frequency(sym.lower(), "en") > 4.0


def clean(raw: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for symbol in raw:
        sym = symbol.strip().upper().replace(".", "/")

        # Ein-Buchstaben-Ticker
        if len(sym) == 1:
            if sym in KEEP_SINGLE:
                out.add(sym)
            continue

        # Länge / Slash-Variante (BRK/B)
        if "/" in sym:
            left, _, right = sym.partition("/")
            if not (1 <= len(left) <= 4 and len(right) == 1):
                continue
        elif not (2 <= len(sym) <= 5):
            continue

        # Nur Buchstaben
        if not (sym.isalpha() or "/" in sym):
            continue

        # Stop-Wörter
        if sym in MANUAL_STOP or _looks_like_word(sym):
            continue

        out.add(sym)
    return out


def verify_with_yf(symbols: set[str], workers: int = 32) -> set[str]:
    
    if yf is None:
        logging.warning("yfinance nicht installiert – Verify übersprungen.")
        return symbols

    def _ok(s: str) -> bool:
        try:
            return bool(yf.Ticker(s).fast_info)
        except Exception:
            return False

    good: set[str] = set()
    with cf.ThreadPoolExecutor(workers) as ex:
        for sym, ok in zip(symbols, ex.map(_ok, symbols)):
            if ok:
                good.add(sym)

    logging.info("Verify: %d / %d Symbole gültig", len(good), len(symbols))
    return good


# --------------------------------------------------------------------------- #
def write_csv(symbols: Iterable[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["symbol"])
        for s in sorted(symbols):
            wr.writerow([s])
    logging.info("→ %s (%d Symbole)", path, len(list(symbols)))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_cli() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Erzeuge White-List für den Reddit-Crawler",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--markets", default="us,de,cn",
                    help="Komma-Liste: us,de,cn,crypto")
    ap.add_argument("--top-crypto", type=int, default=250,
                    help="Top-Coins (CoinGecko) bei crypto-Markt")
    ap.add_argument("--verify", action="store_true",
                    help="Symbole via Yahoo Finance verifizieren (langsam)")
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = parse_cli()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )

    wanted = {m.strip().lower() for m in args.markets.split(",")}
    logging.info("Märkte: %s", ", ".join(sorted(wanted)))

    symbols: set[str] = set()

    if "us" in wanted:
        symbols |= fetch_nasdaq()
        symbols |= fetch_sp500()
    if "de" in wanted:
        symbols |= fetch_germany()
    if "cn" in wanted:
        symbols |= fetch_china_adr()
    if "crypto" in wanted:
        symbols |= fetch_crypto(args.top_crypto)

    logging.info("Roh-Universe: %d Symbole", len(symbols))
    symbols = clean(symbols)

    if args.verify:
        symbols = verify_with_yf(symbols)

    write_csv(symbols, OUT_FILE)
    logging.info("Fertig.")


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Abbruch durch Benutzer")
    except Exception as exc:
        logging.critical("Fehler: %s", exc, exc_info=True)
        sys.exit(1)
